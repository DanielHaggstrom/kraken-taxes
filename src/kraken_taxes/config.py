from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
import tomllib


@dataclass(frozen=True, slots=True)
class TaxBracketConfig:
    up_to: Decimal | None
    rate: Decimal


@dataclass(frozen=True, slots=True)
class TaxConfig:
    profile: str
    starting_taxable_base: Decimal = Decimal("0")
    taxable_basis: str | None = None
    flat_rate: Decimal | None = None
    brackets: tuple[TaxBracketConfig, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class AppConfig:
    config_path: Path
    ledger_dir: Path
    ledger_glob: str
    target_currency: str
    source_timezone: str
    output_timezone: str
    pricing_provider: str
    price_cache_path: Path
    initial_trade_window_seconds: int
    max_trade_window_seconds: int
    route_max_hops: int
    preferred_intermediates: tuple[str, ...] = field(default_factory=tuple)
    http_timeout_seconds: int = 20
    tax: TaxConfig = field(default_factory=lambda: TaxConfig(profile="none"))


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path).resolve()
    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file does not exist: {config_path}. "
            "Create `config/local.toml` from `config/example.toml`."
        )

    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    inputs = raw.get("inputs", {})
    project = raw.get("project", {})
    pricing = raw.get("pricing", {})
    tax = raw.get("tax", {})

    ledger_dir = Path(inputs["ledger_dir"]).expanduser()
    price_cache_path = Path(pricing.get("price_cache_path", ".cache/kraken_price_cache.json"))
    if not price_cache_path.is_absolute():
        price_cache_path = (config_path.parent.parent / price_cache_path).resolve()

    return AppConfig(
        config_path=config_path,
        ledger_dir=ledger_dir,
        ledger_glob=inputs.get("ledger_glob", "*.csv"),
        target_currency=str(project.get("target_currency", "EUR")).upper(),
        source_timezone=project.get("source_timezone", "UTC"),
        output_timezone=project.get("output_timezone", "UTC"),
        pricing_provider=str(pricing.get("provider", "kraken")).lower(),
        price_cache_path=price_cache_path,
        initial_trade_window_seconds=int(pricing.get("initial_trade_window_seconds", 300)),
        max_trade_window_seconds=int(pricing.get("max_trade_window_seconds", 86400)),
        route_max_hops=int(pricing.get("route_max_hops", 2)),
        preferred_intermediates=tuple(
            str(asset).upper() for asset in pricing.get("preferred_intermediates", [])
        ),
        http_timeout_seconds=int(pricing.get("http_timeout_seconds", 20)),
        tax=_load_tax_config(tax),
    )


def ensure_runtime_paths(config: AppConfig) -> None:
    config.price_cache_path.parent.mkdir(parents=True, exist_ok=True)


def _load_tax_config(raw: dict[str, object]) -> TaxConfig:
    profile = str(raw.get("profile", "none")).lower()
    taxable_basis = raw.get("taxable_basis")
    flat_rate = raw.get("flat_rate")
    starting_taxable_base = _to_decimal(raw.get("starting_taxable_base", "0"))

    brackets: list[TaxBracketConfig] = []
    for bracket in raw.get("brackets", []):
        if not isinstance(bracket, dict):
            raise ValueError("Each tax bracket must be a TOML table.")
        up_to_value = bracket.get("up_to")
        brackets.append(
            TaxBracketConfig(
                up_to=None if up_to_value is None else _to_decimal(up_to_value),
                rate=_to_decimal(bracket["rate"]),
            )
        )

    return TaxConfig(
        profile=profile,
        starting_taxable_base=starting_taxable_base,
        taxable_basis=None if taxable_basis is None else str(taxable_basis),
        flat_rate=None if flat_rate is None else _to_decimal(flat_rate),
        brackets=tuple(brackets),
    )


def _to_decimal(value: object) -> Decimal:
    return Decimal(str(value))
