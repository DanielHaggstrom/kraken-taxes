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

