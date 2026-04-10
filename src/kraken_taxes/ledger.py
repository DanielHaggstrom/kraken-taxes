from __future__ import annotations

from collections import Counter
import csv
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from .config import AppConfig
from .models import LedgerEntry, LedgerLoadStats
from .timezones import resolve_timezone


CSV_FIELDS = (
    "txid",
    "refid",
    "time",
    "type",
    "subtype",
    "aclass",
    "subclass",
    "asset",
    "wallet",
    "amount",
    "fee",
    "balance",
)

ASSET_ALIASES = {
    "XXBT": "BTC",
    "XBT": "BTC",
    "XETH": "ETH",
    "ETH": "ETH",
    "ZEUR": "EUR",
    "EUR": "EUR",
    "ZUSD": "USD",
    "USD": "USD",
    "ZGBP": "GBP",
    "GBP": "GBP",
    "ZCAD": "CAD",
    "CAD": "CAD",
    "ZJPY": "JPY",
    "JPY": "JPY",
    "XDG": "DOGE",
}


def normalize_asset_code(raw: str) -> str:
    cleaned = raw.strip().upper()
    if cleaned.endswith(".HOLD"):
        cleaned = cleaned.removesuffix(".HOLD")
    return ASSET_ALIASES.get(cleaned, cleaned)


def discover_ledger_files(config: AppConfig) -> list[Path]:
    if not config.ledger_dir.exists():
        raise FileNotFoundError(f"No existe la carpeta de ledgers: {config.ledger_dir}")
    return sorted(path for path in config.ledger_dir.glob(config.ledger_glob) if path.is_file())


def load_ledgers(config: AppConfig) -> tuple[list[LedgerEntry], LedgerLoadStats]:
    timezone = resolve_timezone(config.source_timezone)
    files = discover_ledger_files(config)
    if not files:
        raise FileNotFoundError(
            f"No se encontraron CSV en {config.ledger_dir} con el patrón {config.ledger_glob!r}."
        )

    source_rows = 0
    duplicates_skipped = 0
    dedup: dict[str, LedgerEntry] = {}

    for file_path in files:
        with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for index, row in enumerate(reader, start=2):
                source_rows += 1
                entry = _row_to_entry(row, file_path, index, timezone)
                key = build_dedup_key(row)
                if key in dedup:
                    duplicates_skipped += 1
                    continue
                dedup[key] = entry

    entries = sorted(dedup.values(), key=lambda item: (item.time, item.txid, item.source_line))
    stats = LedgerLoadStats(
        source_files=tuple(files),
        source_rows=source_rows,
        unique_rows=len(entries),
        duplicates_skipped=duplicates_skipped,
        first_timestamp=entries[0].time if entries else None,
        last_timestamp=entries[-1].time if entries else None,
    )
    return entries, stats


def build_dedup_key(row: dict[str, str]) -> str:
    txid = (row.get("txid") or "").strip()
    if txid:
        return txid

    fingerprint = "|".join((row.get(field) or "").strip() for field in CSV_FIELDS)
    return sha256(fingerprint.encode("utf-8")).hexdigest()


def _row_to_entry(
    row: dict[str, str],
    source_file: Path,
    source_line: int,
    timezone,
) -> LedgerEntry:
    timestamp = datetime.strptime(row["time"].strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone)
    return LedgerEntry(
        txid=row["txid"].strip(),
        refid=row["refid"].strip(),
        time=timestamp,
        type=row["type"].strip(),
        subtype=row["subtype"].strip(),
        aclass=row["aclass"].strip(),
        subclass=row["subclass"].strip(),
        asset=row["asset"].strip(),
        asset_normalized=normalize_asset_code(row["asset"]),
        wallet=row["wallet"].strip(),
        amount=Decimal(row["amount"].strip()),
        fee=Decimal(row["fee"].strip()),
        balance=Decimal(row["balance"].strip()),
        source_file=source_file,
        source_line=source_line,
    )


def summarize_types(entries: list[LedgerEntry]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for entry in entries:
        counter[f"{entry.type}/{entry.subtype or '-'} ({entry.asset_normalized})"] += 1
    return counter


def summarize_assets(entries: list[LedgerEntry]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for entry in entries:
        counter[entry.asset_normalized] += 1
    return counter


def export_merged_ledger(entries: list[LedgerEntry], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                *CSV_FIELDS,
                "normalized_asset",
                "source_file",
                "source_line",
            ],
        )
        writer.writeheader()
        for entry in entries:
            writer.writerow(
                {
                    "txid": entry.txid,
                    "refid": entry.refid,
                    "time": entry.time.strftime("%Y-%m-%d %H:%M:%S"),
                    "type": entry.type,
                    "subtype": entry.subtype,
                    "aclass": entry.aclass,
                    "subclass": entry.subclass,
                    "asset": entry.asset,
                    "wallet": entry.wallet,
                    "amount": str(entry.amount),
                    "fee": str(entry.fee),
                    "balance": str(entry.balance),
                    "normalized_asset": entry.asset_normalized,
                    "source_file": entry.source_file.name,
                    "source_line": entry.source_line,
                }
            )
