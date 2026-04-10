from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path
import sys

from .config import ensure_runtime_paths, load_config
from .ledger import export_merged_ledger, load_ledgers, summarize_assets, summarize_types
from .kraken import KrakenPublicClient
from .pricing import KrakenPriceProvider, PricingError
from .reporting import aggregate_reward_totals, build_reward_report, export_rewards_csv
from .timezones import resolve_timezone


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kraken-taxes",
        description="Consolida ledgers de Kraken y valora recompensas en una divisa objetivo.",
    )
    parser.add_argument(
        "--config",
        default="config/local.toml",
        help="Ruta al fichero de configuración TOML. Por defecto: config/local.toml",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("summary", help="Muestra un resumen del ledger consolidado.")

    merge_parser = subparsers.add_parser("merge", help="Exporta un ledger fusionado y deduplicado.")
    merge_parser.add_argument(
        "--output",
        default="exports/merged-ledger.csv",
        help="Ruta del CSV consolidado de salida.",
    )

    rewards_parser = subparsers.add_parser(
        "rewards",
        help="Valora recompensas earn/reward en la divisa objetivo.",
    )
    rewards_parser.add_argument(
        "--asset",
        action="append",
        help="Activo a incluir. Repetible. Ejemplo: --asset ETH --asset BTC",
    )
    rewards_parser.add_argument(
        "--year",
        type=int,
        help="Filtra por año usando la zona horaria de salida configurada.",
    )
    rewards_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Número de filas a mostrar por consola. Por defecto: 20",
    )
    rewards_parser.add_argument(
        "--output",
        help="Ruta opcional para exportar el reporte completo a CSV.",
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
            print(f"Ledger fusionado exportado a {output_path}")
            return 0

        if args.command == "rewards":
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
            finally:
                provider.save_cache()

            if args.output:
                export_rewards_csv(rewards, Path(args.output), config)
                print(f"Reporte completo exportado a {args.output}")

            _print_rewards(rewards, config, limit=args.limit)
            return 0
    except PricingError as exc:
        print(f"Error de valoración: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    parser.print_help()
    return 1


def _print_summary(config, entries, stats) -> None:
    print("Resumen del ledger")
    print(f"Config: {config.config_path}")
    print(f"Carpeta: {config.ledger_dir}")
    print(f"Ficheros detectados: {len(stats.source_files)}")
    print(f"Filas leídas: {stats.source_rows}")
    print(f"Filas únicas: {stats.unique_rows}")
    print(f"Duplicados descartados: {stats.duplicates_skipped}")
    if stats.first_timestamp and stats.last_timestamp:
        print(f"Rango: {stats.first_timestamp.isoformat()} -> {stats.last_timestamp.isoformat()}")

    print("\nTop movimientos por tipo")
    for name, count in summarize_types(entries).most_common(10):
        print(f"  {count:>4}  {name}")

    print("\nTop activos")
    for name, count in summarize_assets(entries).most_common(10):
        print(f"  {count:>4}  {name}")


def _print_rewards(rewards, config, limit: int) -> None:
    output_tz = resolve_timezone(config.output_timezone)
    print(f"Recompensas valoradas: {len(rewards)}")
    if not rewards:
        return

    totals = aggregate_reward_totals(rewards)
    overall_gross = sum((bucket["gross"] for bucket in totals.values()), start=Decimal("0"))
    overall_fee = sum((bucket["fee"] for bucket in totals.values()), start=Decimal("0"))
    overall_net = sum((bucket["net"] for bucket in totals.values()), start=Decimal("0"))

    print(
        f"Totales {config.target_currency}: bruto={overall_gross} "
        f"fee={overall_fee} neto={overall_net}"
    )
    print("Por activo:")
    for asset, bucket in sorted(totals.items()):
        print(
            f"  {asset}: eventos={bucket['count']} bruto={bucket['gross']} "
            f"fee={bucket['fee']} neto={bucket['net']}"
        )

    print("\nPrimeras filas")
    header = (
        f"{'fecha':19} {'asset':6} {'bruto':14} {'fee':14} "
        f"{'neto':14} {'rate':14} {'valor neto':12} ruta"
    )
    print(header)
    print("-" * len(header))
    for reward in rewards[: max(limit, 0)]:
        local_time = reward.entry.time.astimezone(output_tz).strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"{local_time:19} "
            f"{reward.entry.asset_normalized:6} "
            f"{str(reward.entry.amount):14} "
            f"{str(reward.entry.fee):14} "
            f"{str(reward.entry.net_amount):14} "
            f"{str(reward.quote.rate):14} "
            f"{str(reward.net_value):12} "
            f"{reward.quote.route}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
