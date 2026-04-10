from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from kraken_taxes.config import AppConfig, TaxConfig
from kraken_taxes.models import AssetPair, Trade
from kraken_taxes.pricing import KrakenPriceProvider


def make_config(base_dir: Path) -> AppConfig:
    return AppConfig(
        config_path=base_dir / "config.toml",
        ledger_dir=base_dir,
        ledger_glob="*.csv",
        target_currency="EUR",
        source_timezone="UTC",
        output_timezone="UTC",
        pricing_provider="kraken",
        price_cache_path=base_dir / ".cache" / "prices.json",
        initial_trade_window_seconds=30,
        max_trade_window_seconds=300,
        route_max_hops=2,
        preferred_intermediates=("EUR", "USD"),
        http_timeout_seconds=20,
        tax=TaxConfig(profile="none"),
    )


class FakeKrakenClient:
    def __init__(self) -> None:
        self.asset_pairs = (
            AssetPair("ETHEUR", "ETH/EUR", "XETH", "ZEUR", "online"),
            AssetPair("DOGEUSD", "DOGE/USD", "XDG", "ZUSD", "online"),
            AssetPair("USDEUR", "USD/EUR", "ZUSD", "ZEUR", "online"),
        )
        self.trades = {
            "ETHEUR": (
                Trade(Decimal("3000"), Decimal("1"), 1735732802.0, "b", "m", 1),
            ),
            "DOGEUSD": (
                Trade(Decimal("0.10"), Decimal("1"), 1735732801.0, "b", "m", 2),
            ),
            "USDEUR": (
                Trade(Decimal("0.92"), Decimal("1"), 1735732801.0, "b", "m", 3),
            ),
        }

    def get_asset_pairs(self):
        return self.asset_pairs

    def get_recent_trades(self, pair: str, since: int | str):
        floor = float(since)
        return tuple(trade for trade in self.trades[pair] if trade.timestamp >= floor), "0"


class PricingTests(unittest.TestCase):
    def test_direct_quote_uses_trade_price(self) -> None:
        with TemporaryDirectory() as tmp:
            provider = KrakenPriceProvider(FakeKrakenClient(), make_config(Path(tmp)))
            at_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)

            quote = provider.get_quote("ETH", "EUR", at_time)

            self.assertEqual(quote.rate, Decimal("3000"))
            self.assertEqual(quote.route, "ETH -> EUR")

    def test_two_hop_route_multiplies_rates(self) -> None:
        with TemporaryDirectory() as tmp:
            provider = KrakenPriceProvider(FakeKrakenClient(), make_config(Path(tmp)))
            at_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)

            quote = provider.get_quote("DOGE", "EUR", at_time)

            self.assertEqual(quote.rate, Decimal("0.0920"))
            self.assertEqual(quote.route, "DOGE -> USD -> EUR")


if __name__ == "__main__":
    unittest.main()
