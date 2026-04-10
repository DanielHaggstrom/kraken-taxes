from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
import unittest

from kraken_taxes.config import TaxBracketConfig, TaxConfig
from kraken_taxes.models import LedgerEntry, PriceQuote, RewardValuation
from kraken_taxes.tax import apply_tax_estimates, resolve_tax_profile


def make_reward(gross_value: str, txid: str) -> RewardValuation:
    gross = Decimal(gross_value)
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
        amount=Decimal("0.1"),
        fee=Decimal("0"),
        balance=Decimal("0.1"),
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
        gross_value=gross,
        fee_value=Decimal("0"),
        net_value=gross,
    )


class TaxTests(unittest.TestCase):
    def test_progressive_tax_profile_uses_starting_base(self) -> None:
        profile = resolve_tax_profile(
            TaxConfig(
                profile="progressive",
                taxable_basis="gross_value",
                starting_taxable_base=Decimal("5900"),
                brackets=(
                    TaxBracketConfig(up_to=Decimal("6000"), rate=Decimal("0.10")),
                    TaxBracketConfig(up_to=None, rate=Decimal("0.20")),
                ),
            )
        )

        rewards = apply_tax_estimates(
            [make_reward("200.00", "TX-1"), make_reward("300.00", "TX-2")],
            profile,
        )

        self.assertEqual(rewards[0].estimated_tax, Decimal("30.00"))
        self.assertEqual(rewards[1].estimated_tax, Decimal("60.00"))
        self.assertEqual(rewards[1].cumulative_taxable_base, Decimal("6400.00"))


if __name__ == "__main__":
    unittest.main()
