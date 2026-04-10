from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
import unittest

from kraken_taxes.config import AppConfig
from kraken_taxes.models import LedgerEntry, PriceQuote
from kraken_taxes.reporting import aggregate_reward_totals, build_reward_report


def make_config() -> AppConfig:
    root = Path.cwd()
    return AppConfig(
        config_path=root / "config.toml",
        ledger_dir=root,
        ledger_glob="*.csv",
        target_currency="EUR",
        source_timezone="UTC",
        output_timezone="UTC",
        pricing_provider="kraken",
        price_cache_path=root / ".cache" / "prices.json",
        initial_trade_window_seconds=60,
        max_trade_window_seconds=3600,
        route_max_hops=2,
        preferred_intermediates=("EUR", "USD"),
        http_timeout_seconds=20,
    )


class FakeProvider:
    def get_quote(self, from_asset: str, to_asset: str, at_time: datetime) -> PriceQuote:
        return PriceQuote(
            from_asset=from_asset,
            to_asset=to_asset,
            rate=Decimal("2000"),
            timestamp=at_time,
            steps=(),
        )


class ReportingTests(unittest.TestCase):
    def test_reward_report_values_gross_fee_and_net(self) -> None:
        reward = LedgerEntry(
            txid="TX-001",
            refid="REF-001",
            time=datetime(2025, 1, 6, 16, 29, 16, tzinfo=UTC),
            type="earn",
            subtype="reward",
            aclass="currency",
            subclass="crypto",
            asset="ETH",
            asset_normalized="ETH",
            wallet="spot / main",
            amount=Decimal("0.10"),
            fee=Decimal("0.025"),
            balance=Decimal("0.075"),
            source_file=Path("sample.csv"),
            source_line=2,
        )
        allocation = LedgerEntry(
            txid="TX-002",
            refid="REF-002",
            time=datetime(2025, 1, 7, 16, 29, 16, tzinfo=UTC),
            type="earn",
            subtype="allocation",
            aclass="currency",
            subclass="crypto",
            asset="ETH",
            asset_normalized="ETH",
            wallet="earn / locked",
            amount=Decimal("1"),
            fee=Decimal("0"),
            balance=Decimal("1"),
            source_file=Path("sample.csv"),
            source_line=3,
        )

        report = build_reward_report([reward, allocation], FakeProvider(), make_config(), {"ETH"}, 2025)

        self.assertEqual(len(report), 1)
        self.assertEqual(report[0].gross_value, Decimal("200.00"))
        self.assertEqual(report[0].fee_value, Decimal("50.00"))
        self.assertEqual(report[0].net_value, Decimal("150.00"))

        totals = aggregate_reward_totals(report)
        self.assertEqual(totals["ETH"]["count"], 1)
        self.assertEqual(totals["ETH"]["gross"], Decimal("200.00"))
        self.assertEqual(totals["ETH"]["fee"], Decimal("50.00"))
        self.assertEqual(totals["ETH"]["net"], Decimal("150.00"))


if __name__ == "__main__":
    unittest.main()
