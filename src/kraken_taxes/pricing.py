from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from decimal import Decimal
from pathlib import Path

from .config import AppConfig
from .kraken import KrakenPublicClient
from .ledger import normalize_asset_code
from .models import AssetPair, ConversionStep, PriceQuote, Trade


class PricingError(RuntimeError):
    """Raised when a price cannot be resolved."""


@dataclass(frozen=True, slots=True)
class PairDirection:
    from_asset: str
    to_asset: str
    pair: str
    pair_base: str
    pair_quote: str
    inverted: bool


class KrakenPriceProvider:
    def __init__(self, client: KrakenPublicClient, config: AppConfig) -> None:
        self.client = client
        self.config = config
        self._graph = self._build_graph(client.get_asset_pairs())
        self._cache = self._load_cache(config.price_cache_path)
        self._cache_dirty = False

    def get_quote(self, from_asset: str, to_asset: str, at_time: datetime) -> PriceQuote:
        source = normalize_asset_code(from_asset)
        target = normalize_asset_code(to_asset)
        timestamp = at_time.astimezone(UTC)
        if source == target:
            return PriceQuote(
                from_asset=source,
                to_asset=target,
                rate=Decimal("1"),
                timestamp=timestamp,
                steps=(),
            )

        route = self._find_route(source, target)
        rate = Decimal("1")
        steps: list[ConversionStep] = []

        for edge in route:
            trade_price, trade_time = self._get_pair_price(edge.pair, timestamp)
            effective_rate = Decimal("1") / trade_price if edge.inverted else trade_price
            rate *= effective_rate
            steps.append(
                ConversionStep(
                    from_asset=edge.from_asset,
                    to_asset=edge.to_asset,
                    pair=edge.pair,
                    pair_base=edge.pair_base,
                    pair_quote=edge.pair_quote,
                    inverted=edge.inverted,
                    trade_price=trade_price,
                    effective_rate=effective_rate,
                    trade_time=trade_time,
                )
            )

        return PriceQuote(
            from_asset=source,
            to_asset=target,
            rate=rate,
            timestamp=timestamp,
            steps=tuple(steps),
        )

    def save_cache(self) -> None:
        if not self._cache_dirty:
            return

        self.config.price_cache_path.parent.mkdir(parents=True, exist_ok=True)
        serializable = {
            key: {
                "price": value["price"],
                "trade_time": value["trade_time"],
            }
            for key, value in sorted(self._cache.items())
        }
        payload = {"version": 1, "quotes": serializable}
        self.config.price_cache_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        self._cache_dirty = False

    def _find_route(self, source: str, target: str) -> tuple[PairDirection, ...]:
        queue: deque[tuple[str, tuple[PairDirection, ...]]] = deque([(source, ())])
        visited = {source}

        while queue:
            asset, path = queue.popleft()
            if len(path) >= self.config.route_max_hops:
                continue

            edges = sorted(
                self._graph.get(asset, ()),
                key=lambda edge: self._edge_priority(edge, target),
            )
            for edge in edges:
                next_path = path + (edge,)
                if edge.to_asset == target:
                    return next_path
                if edge.to_asset in visited:
                    continue
                visited.add(edge.to_asset)
                queue.append((edge.to_asset, next_path))

        raise PricingError(f"No se encontró ruta de conversión en Kraken: {source} -> {target}")

    def _edge_priority(self, edge: PairDirection, target: str) -> tuple[int, int, str]:
        if edge.to_asset == target:
            return (0, 0, edge.pair)
        if edge.to_asset in self.config.preferred_intermediates:
            return (1, self.config.preferred_intermediates.index(edge.to_asset), edge.pair)
        return (2, 999, edge.pair)

    def _get_pair_price(self, pair: str, at_time: datetime) -> tuple[Decimal, datetime]:
        key = f"{pair}|{int(at_time.timestamp())}"
        cached = self._cache.get(key)
        if cached:
            return Decimal(cached["price"]), datetime.fromisoformat(cached["trade_time"])

        best_trade: Trade | None = None
        best_delta: float | None = None
        event_seconds = at_time.timestamp()
        window = max(1, self.config.initial_trade_window_seconds)

        while window <= self.config.max_trade_window_seconds:
            since = max(0, int(event_seconds - window))
            trades, _ = self.client.get_recent_trades(pair, since)
            candidate = _pick_closest_trade(trades, event_seconds)
            if candidate is not None:
                delta = abs(candidate.timestamp - event_seconds)
                if best_delta is None or delta < best_delta:
                    best_trade = candidate
                    best_delta = delta
                if delta <= window:
                    break
            window *= 2

        if best_trade is None or best_delta is None or best_delta > self.config.max_trade_window_seconds:
            raise PricingError(
                f"No se encontró trade suficientemente cercano para {pair} en {at_time.isoformat()}."
            )

        trade_time = datetime.fromtimestamp(best_trade.timestamp, tz=UTC)
        self._cache[key] = {"price": str(best_trade.price), "trade_time": trade_time.isoformat()}
        self._cache_dirty = True
        return best_trade.price, trade_time

    def _build_graph(
        self,
        asset_pairs: tuple[AssetPair, ...],
    ) -> dict[str, tuple[PairDirection, ...]]:
        graph: dict[str, list[PairDirection]] = defaultdict(list)
        for pair in asset_pairs:
            if pair.status != "online":
                continue
            base = normalize_asset_code(pair.base)
            quote = normalize_asset_code(pair.quote)
            graph[base].append(
                PairDirection(
                    from_asset=base,
                    to_asset=quote,
                    pair=pair.altname,
                    pair_base=base,
                    pair_quote=quote,
                    inverted=False,
                )
            )
            graph[quote].append(
                PairDirection(
                    from_asset=quote,
                    to_asset=base,
                    pair=pair.altname,
                    pair_base=base,
                    pair_quote=quote,
                    inverted=True,
                )
            )
        return {key: tuple(value) for key, value in graph.items()}

    def _load_cache(self, path: Path) -> dict[str, dict[str, str]]:
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {str(key): value for key, value in payload.get("quotes", {}).items()}


def _pick_closest_trade(trades: tuple[Trade, ...], event_seconds: float) -> Trade | None:
    if not trades:
        return None
    return min(trades, key=lambda trade: abs(trade.timestamp - event_seconds))

