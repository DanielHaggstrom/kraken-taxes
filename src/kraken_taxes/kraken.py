from __future__ import annotations

import json
from decimal import Decimal
from http.client import IncompleteRead
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import AssetPair, Trade


class KrakenApiError(RuntimeError):
    """Raised when Kraken returns an API error."""


class KrakenPublicClient:
    def __init__(self, timeout_seconds: int = 20) -> None:
        self.base_url = "https://api.kraken.com/0/public"
        self.timeout_seconds = timeout_seconds
        self._asset_pairs: tuple[AssetPair, ...] | None = None
        self._last_request_monotonic = 0.0
        self._min_request_interval_seconds = 1.2

    def get_asset_pairs(self) -> tuple[AssetPair, ...]:
        if self._asset_pairs is not None:
            return self._asset_pairs

        payload = self._request("/AssetPairs")
        pairs: list[AssetPair] = []
        for value in payload.values():
            pairs.append(
                AssetPair(
                    altname=value["altname"],
                    wsname=value.get("wsname", value["altname"]),
                    base=value["base"],
                    quote=value["quote"],
                    status=value.get("status", "unknown"),
                )
            )

        self._asset_pairs = tuple(pairs)
        return self._asset_pairs

    def get_recent_trades(self, pair: str, since: int | str) -> tuple[tuple[Trade, ...], str]:
        payload = self._request("/Trades", {"pair": pair, "since": since})
        pair_key = next(key for key in payload if key != "last")
        raw_trades = payload[pair_key]
        trades = tuple(
            Trade(
                price=Decimal(item[0]),
                volume=Decimal(item[1]),
                timestamp=float(item[2]),
                side=item[3],
                order_type=item[4],
                trade_id=int(item[6]),
            )
            for item in raw_trades
        )
        return trades, str(payload["last"])

    def _request(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        query = urlencode(params or {})
        url = f"{self.base_url}{endpoint}"
        if query:
            url = f"{url}?{query}"

        request = Request(url, headers={"User-Agent": "kraken-taxes/0.1.0"})
        for attempt in range(6):
            self._respect_rate_limit()
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    payload = json.load(response)
            except (HTTPError, URLError, IncompleteRead, TimeoutError) as exc:
                if attempt == 5:
                    raise KrakenApiError(str(exc)) from exc
                time.sleep(min(2**attempt, 10))
                continue

            errors = payload.get("error", [])
            if errors and any("Too many requests" in error for error in errors):
                if attempt == 5:
                    raise KrakenApiError("; ".join(errors))
                time.sleep(min(2**attempt, 10))
                continue
            if errors:
                raise KrakenApiError("; ".join(errors))
            return payload["result"]

        raise KrakenApiError("No se pudo completar la petición a Kraken.")

    def _respect_rate_limit(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_request_monotonic
        remaining = self._min_request_interval_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self._last_request_monotonic = time.monotonic()
