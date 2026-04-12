from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from kraken_taxes.config import AppConfig, TaxConfig
from kraken_taxes.html_report import export_reward_report_html
from kraken_taxes.models import (
    LedgerEntry,
    PriceCacheStats,
    PriceQuote,
    RewardReportSummary,
    RewardValuation,
)


def make_config(root: Path) -> AppConfig:
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
        tax=TaxConfig(profile="none"),
    )


def make_reward(txid: str, gross_value: str, estimated_tax: str) -> RewardValuation:
    entry = LedgerEntry(
        txid=txid,
        refid=f"REF-{txid}",
        time=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        type="earn",
        subtype="reward",
        aclass="currency",
        subclass="crypto",
        asset="ETH",
        asset_normalized="ETH",
        wallet="spot / main",
        amount=Decimal("0.001"),
        fee=Decimal("0"),
        balance=Decimal("0.001"),
        source_file=Path("sample.csv"),
        source_line=2,
    )
    quote = PriceQuote(
        from_asset="ETH",
        to_asset="EUR",
        rate=Decimal("1"),
        timestamp=entry.time,
        steps=(),
    )
    return RewardValuation(
        entry=entry,
        target_currency="EUR",
        quote=quote,
        gross_value=Decimal(gross_value),
        fee_value=Decimal("0"),
        net_value=Decimal(gross_value),
        taxable_value=Decimal(gross_value),
        estimated_tax=Decimal(estimated_tax),
    )


class HtmlReportTests(unittest.TestCase):
    def test_html_report_contains_audit_section_and_micro_event_counts(self) -> None:
        rewards = [
            make_reward("TX-1", "0.005", "0.001"),
            make_reward("TX-2", "0.005", "0.001"),
        ]
        summary = RewardReportSummary(
            target_currency="EUR",
            tax_profile="none",
            taxable_basis="gross_value",
            event_count=2,
            starting_taxable_base=Decimal("0"),
            gross_value=Decimal("0.01"),
            fee_value=Decimal("0.00"),
            net_value=Decimal("0.01"),
            taxable_value=Decimal("0.01"),
            estimated_tax=Decimal("0.00"),
            effective_tax_rate=Decimal("0"),
            asset_summaries=(),
            monthly_summaries=(),
            tax_profile_display_name="No tax estimation",
            tax_profile_kind="none",
            tax_profile_notes="Notes",
            tax_profile_references=(),
        )

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_path = root / "report.html"
            export_reward_report_html(
                rewards,
                summary,
                output_path,
                make_config(root),
                PriceCacheStats(entries_loaded=0, cache_hits=0, cache_misses=0),
                max_event_rows=10,
            )

            html = output_path.read_text(encoding="utf-8")
            self.assertIn("Audit checks", html)
            self.assertIn("Micro-events below 0.01 EUR", html)
            self.assertIn("gross=2", html)
            self.assertIn("0.005", html)


if __name__ == "__main__":
    unittest.main()
