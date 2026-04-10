from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path
import sys

from .config import ensure_runtime_paths, load_config
from .html_report import export_reward_report_html
from .ledger import export_merged_ledger, load_ledgers, summarize_assets, summarize_types
from .kraken import KrakenPublicClient
from .pricing import KrakenPriceProvider, PricingError
from .reporting import build_reward_report, build_reward_report_summary, export_rewards_csv
from .timezones import resolve_timezone


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kraken-taxes",
        description="Merge Kraken ledgers and estimate reward values and taxes.",
    )
    parser.add_argument(
        "--config",
        default="config/local.toml",
        help="Path to the TOML configuration file. Default: config/local.toml",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("summary", help="Show a summary of the consolidated ledger.")

    merge_parser = subparsers.add_parser("merge", help="Export a merged, deduplicated ledger.")
    merge_parser.add_argument(
        "--output",
        default="exports/merged-ledger.csv",
        help="Path to the merged CSV output.",
    )

    rewards_parser = subparsers.add_parser(
        "rewards",
        help="Value earn/reward events and print a console summary.",
    )
    _add_reward_filters(rewards_parser)
    rewards_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of rows to show in the console preview. Default: 20",
    )
    rewards_parser.add_argument(
        "--output",
        help="Optional CSV output path for the detailed reward valuation report.",
    )

    report_parser = subparsers.add_parser(
        "report",
        help="Generate CSV and HTML reward reports with tax estimates.",
    )
    _add_reward_filters(report_parser)
    report_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of rows to show in the console preview. Default: 20",
    )
    report_parser.add_argument(
        "--csv-output",
        default="reports/reward-report.csv",
        help="Detailed CSV output path. Default: reports/reward-report.csv",
    )
    report_parser.add_argument(
        "--html-output",
        default="reports/reward-report.html",
        help="HTML output path. Default: reports/reward-report.html",
    )
    report_parser.add_argument(
        "--max-event-rows",
        type=int,
        default=500,
        help="Maximum number of event rows rendered into the HTML report. Default: 500",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        ensure_runtime_paths(config)
        entries, stats = load_ledgers(config)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    try:
        if args.command == "summary":
            _print_summary(config, entries, stats)
            return 0

        if args.command == "merge":
            output_path = Path(args.output)
            export_merged_ledger(entries, output_path)
            print(f"Merged ledger exported to {output_path}")
            return 0

        if args.command in {"rewards", "report"}:
            client = KrakenPublicClient(timeout_seconds=config.http_timeout_seconds)
            provider = KrakenPriceProvider(client, config)
            try:
                rewards = build_reward_report(
                    entries,
                    provider,
                    config,
                    assets=set(args.asset) if args.asset else None,
                    year=args.year,
                )
                summary = build_reward_report_summary(rewards, config)

                if args.command == "rewards" and args.output:
                    export_rewards_csv(rewards, Path(args.output), config)
                    print(f"Detailed CSV report exported to {args.output}")

                if args.command == "report":
                    export_rewards_csv(rewards, Path(args.csv_output), config)
                    export_reward_report_html(
                        rewards,
                        summary,
                        Path(args.html_output),
                        config,
                        provider.get_cache_stats(),
                        max_event_rows=args.max_event_rows,
                    )
                    print(f"Detailed CSV report exported to {args.csv_output}")
                    print(f"HTML report exported to {args.html_output}")
            finally:
                provider.save_cache()

            _print_reward_summary(summary)
            cache_stats = provider.get_cache_stats()
            print(
                f"Price cache: loaded={cache_stats.entries_loaded} "
                f"hits={cache_stats.cache_hits} misses={cache_stats.cache_misses}"
            )
            _print_reward_preview(rewards, config, limit=args.limit)
            return 0
    except PricingError as exc:
        print(f"Pricing error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    parser.print_help()
    return 1


def _add_reward_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--asset",
        action="append",
        help="Asset to include. Repeatable. Example: --asset ETH --asset BTC",
    )
    parser.add_argument(
        "--year",
        type=int,
        help="Filter by calendar year using the configured output timezone.",
    )


def _print_summary(config, entries, stats) -> None:
    print("Consolidated ledger summary")
    print(f"Config: {config.config_path}")
    print(f"Ledger directory: {config.ledger_dir}")
    print(f"Files discovered: {len(stats.source_files)}")
    print(f"Rows read: {stats.source_rows}")
    print(f"Unique rows: {stats.unique_rows}")
    print(f"Duplicates skipped: {stats.duplicates_skipped}")
    print(f"Tax profile: {config.tax.profile}")
    print(f"Price cache: {config.price_cache_path}")
    if stats.first_timestamp and stats.last_timestamp:
        print(f"Range: {stats.first_timestamp.isoformat()} -> {stats.last_timestamp.isoformat()}")

    print("\nTop movement types")
    for name, count in summarize_types(entries).most_common(10):
        print(f"  {count:>4}  {name}")

    print("\nTop assets")
    for name, count in summarize_assets(entries).most_common(10):
        print(f"  {count:>4}  {name}")


def _print_reward_summary(summary) -> None:
    print(f"Reward events valued: {summary.event_count}")
    print(f"Tax profile: {summary.tax_profile_display_name}")
    print(f"Tax basis: {summary.taxable_basis}")
    print(
        f"Totals {summary.target_currency}: gross={summary.gross_value} "
        f"fee={summary.fee_value} net={summary.net_value}"
    )
    print(
        f"Taxable base={summary.taxable_value} "
        f"estimated_tax={summary.estimated_tax} "
        f"effective_rate={summary.effective_tax_rate}"
    )
    print(f"Starting taxable base={summary.starting_taxable_base}")
    print("By asset:")
    for item in summary.asset_summaries:
        print(
            f"  {item.asset}: events={item.event_count} gross_value={item.gross_value} "
            f"taxable_value={item.taxable_value} estimated_tax={item.estimated_tax}"
        )


def _print_reward_preview(rewards, config, limit: int) -> None:
    output_tz = resolve_timezone(config.output_timezone)
    if not rewards or limit <= 0:
        return

    print("\nPreview")
    header = (
        f"{'local_time':25} {'asset':6} {'gross':14} {'gross_value':14} "
        f"{'taxable':12} {'tax':12} route"
    )
    print(header)
    print("-" * len(header))
    for reward in rewards[:limit]:
        local_time = reward.entry.time.astimezone(output_tz).isoformat()
        print(
            f"{local_time:25} "
            f"{reward.entry.asset_normalized:6} "
            f"{str(reward.entry.amount):14} "
            f"{str(reward.gross_value):14} "
            f"{str(reward.taxable_value):12} "
            f"{str(reward.estimated_tax):12} "
            f"{reward.quote.route}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
