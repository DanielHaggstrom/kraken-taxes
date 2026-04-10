from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from kraken_taxes.config import AppConfig
from kraken_taxes.ledger import load_ledgers, normalize_asset_code


def make_config(ledger_dir: Path) -> AppConfig:
    return AppConfig(
        config_path=ledger_dir / "config.toml",
        ledger_dir=ledger_dir,
        ledger_glob="*.csv",
        target_currency="EUR",
        source_timezone="UTC",
        output_timezone="UTC",
        pricing_provider="kraken",
        price_cache_path=ledger_dir / ".cache" / "prices.json",
        initial_trade_window_seconds=60,
        max_trade_window_seconds=3600,
        route_max_hops=2,
        preferred_intermediates=("EUR", "USD"),
        http_timeout_seconds=20,
    )


class LedgerTests(unittest.TestCase):
    def test_normalize_asset_code(self) -> None:
        self.assertEqual(normalize_asset_code("EUR.HOLD"), "EUR")
        self.assertEqual(normalize_asset_code("XXBT"), "BTC")
        self.assertEqual(normalize_asset_code("EIGEN"), "EIGEN")

    def test_load_ledgers_deduplicates_overlapping_exports(self) -> None:
        with TemporaryDirectory() as tmp:
            ledger_dir = Path(tmp)
            file_one = ledger_dir / "part1.csv"
            file_two = ledger_dir / "part2.csv"

            header = (
                "txid,refid,time,type,subtype,aclass,subclass,asset,wallet,amount,fee,balance\n"
            )
            shared = (
                "TX-001,REF-1,2025-01-06 16:29:16,earn,reward,currency,crypto,ETH,"
                "spot / main,0.1000000000,0.0250000000,0.0750000000\n"
            )
            unique = (
                "TX-002,REF-2,2025-01-13 16:29:16,earn,reward,currency,crypto,BTC,"
                "spot / main,0.0100000000,0.0000000000,0.0100000000\n"
            )

            file_one.write_text(header + shared, encoding="utf-8")
            file_two.write_text(header + shared + unique, encoding="utf-8")

            entries, stats = load_ledgers(make_config(ledger_dir))

            self.assertEqual(stats.source_rows, 3)
            self.assertEqual(stats.unique_rows, 2)
            self.assertEqual(stats.duplicates_skipped, 1)
            self.assertEqual([entry.txid for entry in entries], ["TX-001", "TX-002"])


if __name__ == "__main__":
    unittest.main()

