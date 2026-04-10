from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    txid: str
    refid: str
    time: datetime
    type: str
    subtype: str
    aclass: str
    subclass: str
    asset: str
    asset_normalized: str
    wallet: str
    amount: Decimal
    fee: Decimal
    balance: Decimal
    source_file: Path
    source_line: int

    @property
    def net_amount(self) -> Decimal:
        return self.amount - self.fee


@dataclass(frozen=True, slots=True)
class LedgerLoadStats:
    source_files: tuple[Path, ...]
    source_rows: int
    unique_rows: int
    duplicates_skipped: int
    first_timestamp: datetime | None
    last_timestamp: datetime | None


@dataclass(frozen=True, slots=True)
class AssetPair:
    altname: str
    wsname: str
    base: str
    quote: str
    status: str


@dataclass(frozen=True, slots=True)
class Trade:
    price: Decimal
    volume: Decimal
    timestamp: float
    side: str
    order_type: str
    trade_id: int


@dataclass(frozen=True, slots=True)
class ConversionStep:
    from_asset: str
    to_asset: str
    pair: str
    pair_base: str
    pair_quote: str
    inverted: bool
    trade_price: Decimal
    effective_rate: Decimal
    trade_time: datetime


@dataclass(frozen=True, slots=True)
class PriceQuote:
    from_asset: str
    to_asset: str
    rate: Decimal
    timestamp: datetime
    steps: tuple[ConversionStep, ...]

    @property
    def route(self) -> str:
        assets = [self.from_asset, *[step.to_asset for step in self.steps]]
        return " -> ".join(assets)


@dataclass(frozen=True, slots=True)
class RewardValuation:
    entry: LedgerEntry
    target_currency: str
    quote: PriceQuote
    gross_value: Decimal
    fee_value: Decimal
    net_value: Decimal
    taxable_value: Decimal = Decimal("0")
    estimated_tax: Decimal = Decimal("0")
    estimated_tax_rate: Decimal = Decimal("0")
    cumulative_taxable_base: Decimal = Decimal("0")
    tax_profile: str = "none"
    taxable_basis: str = "gross_value"


@dataclass(frozen=True, slots=True)
class PriceCacheStats:
    entries_loaded: int
    cache_hits: int
    cache_misses: int


@dataclass(frozen=True, slots=True)
class AssetRewardSummary:
    asset: str
    event_count: int
    gross_amount: Decimal
    fee_amount: Decimal
    net_amount: Decimal
    gross_value: Decimal
    fee_value: Decimal
    net_value: Decimal
    taxable_value: Decimal
    estimated_tax: Decimal


@dataclass(frozen=True, slots=True)
class MonthlyRewardSummary:
    month: str
    event_count: int
    gross_value: Decimal
    net_value: Decimal
    taxable_value: Decimal
    estimated_tax: Decimal


@dataclass(frozen=True, slots=True)
class RewardReportSummary:
    target_currency: str
    tax_profile: str
    taxable_basis: str
    event_count: int
    starting_taxable_base: Decimal
    gross_value: Decimal
    fee_value: Decimal
    net_value: Decimal
    taxable_value: Decimal
    estimated_tax: Decimal
    effective_tax_rate: Decimal
    asset_summaries: tuple[AssetRewardSummary, ...]
    monthly_summaries: tuple[MonthlyRewardSummary, ...]
    tax_profile_display_name: str
    tax_profile_kind: str
    tax_profile_notes: str
    tax_profile_references: tuple[str, ...]
