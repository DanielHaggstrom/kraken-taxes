from __future__ import annotations

import csv
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from .config import AppConfig
from .models import LedgerEntry, RewardValuation
from .pricing import KrakenPriceProvider
from .timezones import resolve_timezone


MONEY_QUANTIZER = Decimal("0.01")


def build_reward_report(
    entries: list[LedgerEntry],
    provider: KrakenPriceProvider,
    config: AppConfig,
    assets: set[str] | None = None,
    year: int | None = None,
) -> list[RewardValuation]:
    output_tz = resolve_timezone(config.output_timezone)
    normalized_assets = {asset.upper() for asset in assets} if assets else None
    report: list[RewardValuation] = []

    for entry in entries:
        if entry.type != "earn" or entry.subtype != "reward":
            continue
        if normalized_assets and entry.asset_normalized not in normalized_assets:
            continue
        if year and entry.time.astimezone(output_tz).year != year:
            continue

        quote = provider.get_quote(entry.asset_normalized, config.target_currency, entry.time)
        report.append(
            RewardValuation(
                entry=entry,
                target_currency=config.target_currency,
                quote=quote,
                gross_value=quantize_money(entry.amount * quote.rate),
                fee_value=quantize_money(entry.fee * quote.rate),
                net_value=quantize_money(entry.net_amount * quote.rate),
            )
        )

    return report


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTIZER, rounding=ROUND_HALF_UP)


def aggregate_reward_totals(rewards: list[RewardValuation]) -> dict[str, dict[str, Decimal | int]]:
    totals: dict[str, dict[str, Decimal | int]] = {}
    for reward in rewards:
        bucket = totals.setdefault(
            reward.entry.asset_normalized,
            {
                "count": 0,
                "gross": Decimal("0"),
                "fee": Decimal("0"),
                "net": Decimal("0"),
            },
        )
        bucket["count"] = int(bucket["count"]) + 1
        bucket["gross"] = Decimal(bucket["gross"]) + reward.gross_value
        bucket["fee"] = Decimal(bucket["fee"]) + reward.fee_value
        bucket["net"] = Decimal(bucket["net"]) + reward.net_value
    return totals


def export_rewards_csv(
    rewards: list[RewardValuation],
    output_path: Path,
    config: AppConfig,
) -> None:
    utc = resolve_timezone("UTC")
    output_tz = resolve_timezone(config.output_timezone)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "time_utc",
                "time_local",
                "asset",
                "gross_amount",
                "fee_amount",
                "net_amount",
                "target_currency",
                "rate",
                "gross_value",
                "fee_value",
                "net_value",
                "route",
                "trade_times_utc",
                "txid",
                "refid",
                "wallet",
                "source_file",
                "source_line",
            ],
        )
        writer.writeheader()
        for reward in rewards:
            writer.writerow(
                {
                    "time_utc": reward.entry.time.astimezone(utc).isoformat(),
                    "time_local": reward.entry.time.astimezone(output_tz).isoformat(),
                    "asset": reward.entry.asset_normalized,
                    "gross_amount": str(reward.entry.amount),
                    "fee_amount": str(reward.entry.fee),
                    "net_amount": str(reward.entry.net_amount),
                    "target_currency": reward.target_currency,
                    "rate": str(reward.quote.rate),
                    "gross_value": str(reward.gross_value),
                    "fee_value": str(reward.fee_value),
                    "net_value": str(reward.net_value),
                    "route": reward.quote.route,
                    "trade_times_utc": " | ".join(
                        step.trade_time.astimezone(utc).isoformat()
                        for step in reward.quote.steps
                    ),
                    "txid": reward.entry.txid,
                    "refid": reward.entry.refid,
                    "wallet": reward.entry.wallet,
                    "source_file": reward.entry.source_file.name,
                    "source_line": reward.entry.source_line,
                }
            )
