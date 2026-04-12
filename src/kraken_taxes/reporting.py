from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

from .config import AppConfig
from .models import (
    AssetRewardSummary,
    LedgerEntry,
    MonthlyRewardSummary,
    RewardReportSummary,
    RewardValuation,
)
from .pricing import KrakenPriceProvider
from .tax import apply_tax_estimates, quantize_money, quantize_rate, resolve_tax_profile
from .timezones import resolve_timezone


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
                gross_value=entry.amount * quote.rate,
                fee_value=entry.fee * quote.rate,
                net_value=entry.net_amount * quote.rate,
            )
        )

    profile = resolve_tax_profile(config.tax)
    return apply_tax_estimates(report, profile)


def aggregate_reward_totals(rewards: list[RewardValuation]) -> dict[str, dict[str, Decimal | int]]:
    totals: dict[str, dict[str, Decimal | int]] = {}
    for reward in rewards:
        bucket = totals.setdefault(
            reward.entry.asset_normalized,
            {
                "count": 0,
                "gross_amount": Decimal("0"),
                "fee_amount": Decimal("0"),
                "net_amount": Decimal("0"),
                "gross_value": Decimal("0"),
                "fee_value": Decimal("0"),
                "net_value": Decimal("0"),
                "taxable_value": Decimal("0"),
                "estimated_tax": Decimal("0"),
            },
        )
        bucket["count"] = int(bucket["count"]) + 1
        bucket["gross_amount"] = Decimal(bucket["gross_amount"]) + reward.entry.amount
        bucket["fee_amount"] = Decimal(bucket["fee_amount"]) + reward.entry.fee
        bucket["net_amount"] = Decimal(bucket["net_amount"]) + reward.entry.net_amount
        bucket["gross_value"] = Decimal(bucket["gross_value"]) + reward.gross_value
        bucket["fee_value"] = Decimal(bucket["fee_value"]) + reward.fee_value
        bucket["net_value"] = Decimal(bucket["net_value"]) + reward.net_value
        bucket["taxable_value"] = Decimal(bucket["taxable_value"]) + reward.taxable_value
        bucket["estimated_tax"] = Decimal(bucket["estimated_tax"]) + reward.estimated_tax
    return totals


def build_reward_report_summary(
    rewards: list[RewardValuation],
    config: AppConfig,
) -> RewardReportSummary:
    profile = resolve_tax_profile(config.tax)
    asset_totals = aggregate_reward_totals(rewards)
    asset_summaries = tuple(
        AssetRewardSummary(
            asset=asset,
            event_count=int(bucket["count"]),
            gross_amount=Decimal(bucket["gross_amount"]),
            fee_amount=Decimal(bucket["fee_amount"]),
            net_amount=Decimal(bucket["net_amount"]),
            gross_value=quantize_money(Decimal(bucket["gross_value"])),
            fee_value=quantize_money(Decimal(bucket["fee_value"])),
            net_value=quantize_money(Decimal(bucket["net_value"])),
            taxable_value=quantize_money(Decimal(bucket["taxable_value"])),
            estimated_tax=quantize_money(Decimal(bucket["estimated_tax"])),
        )
        for asset, bucket in sorted(asset_totals.items())
    )
    monthly_summaries = build_monthly_summaries(rewards, config)
    gross_value = sum((reward.gross_value for reward in rewards), start=Decimal("0"))
    fee_value = sum((reward.fee_value for reward in rewards), start=Decimal("0"))
    net_value = sum((reward.net_value for reward in rewards), start=Decimal("0"))
    taxable_value = sum((reward.taxable_value for reward in rewards), start=Decimal("0"))
    estimated_tax = sum((reward.estimated_tax for reward in rewards), start=Decimal("0"))
    effective_tax_rate = (
        quantize_rate(estimated_tax / taxable_value) if taxable_value else Decimal("0")
    )

    return RewardReportSummary(
        target_currency=config.target_currency,
        tax_profile=profile.name,
        taxable_basis=profile.taxable_basis,
        event_count=len(rewards),
        starting_taxable_base=profile.starting_taxable_base,
        gross_value=quantize_money(gross_value),
        fee_value=quantize_money(fee_value),
        net_value=quantize_money(net_value),
        taxable_value=quantize_money(taxable_value),
        estimated_tax=quantize_money(estimated_tax),
        effective_tax_rate=effective_tax_rate,
        asset_summaries=asset_summaries,
        monthly_summaries=monthly_summaries,
        tax_profile_display_name=profile.display_name,
        tax_profile_kind=profile.kind,
        tax_profile_notes=profile.notes,
        tax_profile_references=profile.references,
    )


def build_monthly_summaries(
    rewards: list[RewardValuation],
    config: AppConfig,
) -> tuple[MonthlyRewardSummary, ...]:
    output_tz = resolve_timezone(config.output_timezone)
    buckets: dict[str, dict[str, Decimal | int]] = {}

    for reward in rewards:
        month = reward.entry.time.astimezone(output_tz).strftime("%Y-%m")
        bucket = buckets.setdefault(
            month,
            {
                "count": 0,
                "gross_value": Decimal("0"),
                "net_value": Decimal("0"),
                "taxable_value": Decimal("0"),
                "estimated_tax": Decimal("0"),
            },
        )
        bucket["count"] = int(bucket["count"]) + 1
        bucket["gross_value"] = Decimal(bucket["gross_value"]) + reward.gross_value
        bucket["net_value"] = Decimal(bucket["net_value"]) + reward.net_value
        bucket["taxable_value"] = Decimal(bucket["taxable_value"]) + reward.taxable_value
        bucket["estimated_tax"] = Decimal(bucket["estimated_tax"]) + reward.estimated_tax

    return tuple(
        MonthlyRewardSummary(
            month=month,
            event_count=int(bucket["count"]),
            gross_value=quantize_money(Decimal(bucket["gross_value"])),
            net_value=quantize_money(Decimal(bucket["net_value"])),
            taxable_value=quantize_money(Decimal(bucket["taxable_value"])),
            estimated_tax=quantize_money(Decimal(bucket["estimated_tax"])),
        )
        for month, bucket in sorted(buckets.items())
    )


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
                "taxable_value",
                "estimated_tax",
                "estimated_tax_rate",
                "cumulative_taxable_base",
                "tax_profile",
                "taxable_basis",
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
                    "taxable_value": str(reward.taxable_value),
                    "estimated_tax": str(reward.estimated_tax),
                    "estimated_tax_rate": str(reward.estimated_tax_rate),
                    "cumulative_taxable_base": str(reward.cumulative_taxable_base),
                    "tax_profile": reward.tax_profile,
                    "taxable_basis": reward.taxable_basis,
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
