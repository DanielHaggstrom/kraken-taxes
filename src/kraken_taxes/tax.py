from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, ROUND_HALF_UP

from .config import TaxBracketConfig, TaxConfig
from .models import RewardValuation


MONEY_QUANTIZER = Decimal("0.01")
RATE_QUANTIZER = Decimal("0.0001")

SPAIN_STAKING_REFERENCE_URL = "https://www.hacienda.gob.es/sgt/tributos/memorias/memoria-2024.pdf"
SPAIN_IRPF_REFERENCE_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764"


@dataclass(frozen=True, slots=True)
class ResolvedTaxProfile:
    name: str
    display_name: str
    kind: str
    taxable_basis: str
    starting_taxable_base: Decimal
    flat_rate: Decimal | None
    brackets: tuple[TaxBracketConfig, ...]
    notes: str
    references: tuple[str, ...]


def resolve_tax_profile(config: TaxConfig) -> ResolvedTaxProfile:
    profile = config.profile.lower()

    if profile == "none":
        return ResolvedTaxProfile(
            name="none",
            display_name="No tax estimation",
            kind="none",
            taxable_basis=config.taxable_basis or "gross_value",
            starting_taxable_base=config.starting_taxable_base,
            flat_rate=None,
            brackets=(),
            notes=(
                "Tax estimation is disabled. Taxable values are still derived from the "
                "selected basis, but no tax liability is simulated."
            ),
            references=(),
        )

    if profile == "flat":
        if config.flat_rate is None:
            raise ValueError("Tax profile 'flat' requires `flat_rate` in the [tax] section.")
        return ResolvedTaxProfile(
            name="flat",
            display_name="Custom flat tax",
            kind="flat",
            taxable_basis=config.taxable_basis or "gross_value",
            starting_taxable_base=config.starting_taxable_base,
            flat_rate=config.flat_rate,
            brackets=(),
            notes=(
                "Applies a single rate to the configured taxable basis. "
                "The reported tax is an incremental estimate only."
            ),
            references=(),
        )

    if profile == "progressive":
        if not config.brackets:
            raise ValueError("Tax profile 'progressive' requires [[tax.brackets]] entries.")
        return ResolvedTaxProfile(
            name="progressive",
            display_name="Custom progressive tax",
            kind="progressive",
            taxable_basis=config.taxable_basis or "gross_value",
            starting_taxable_base=config.starting_taxable_base,
            flat_rate=None,
            brackets=config.brackets,
            notes=(
                "Applies the configured brackets to the selected taxable basis. "
                "The reported tax is an incremental estimate only."
            ),
            references=(),
        )

    if profile == "spain_irpf_savings_2025":
        return ResolvedTaxProfile(
            name="spain_irpf_savings_2025",
            display_name="Spain IRPF savings base (2025)",
            kind="progressive",
            taxable_basis=config.taxable_basis or "gross_value",
            starting_taxable_base=config.starting_taxable_base,
            flat_rate=None,
            brackets=(
                TaxBracketConfig(up_to=Decimal("6000"), rate=Decimal("0.19")),
                TaxBracketConfig(up_to=Decimal("50000"), rate=Decimal("0.21")),
                TaxBracketConfig(up_to=Decimal("200000"), rate=Decimal("0.23")),
                TaxBracketConfig(up_to=Decimal("300000"), rate=Decimal("0.27")),
                TaxBracketConfig(up_to=None, rate=Decimal("0.30")),
            ),
            notes=(
                "Assumption: reward income is treated as savings-base income in Spain. "
                "For staking rewards, the built-in assumption uses gross market value at receipt. "
                "The reported tax is an incremental estimate only and depends on the configured "
                "starting taxable base."
            ),
            references=(SPAIN_STAKING_REFERENCE_URL, SPAIN_IRPF_REFERENCE_URL),
        )

    raise ValueError(
        f"Unknown tax profile: {config.profile}. "
        "Supported profiles: none, flat, progressive, spain_irpf_savings_2025."
    )


def apply_tax_estimates(
    rewards: list[RewardValuation],
    profile: ResolvedTaxProfile,
) -> list[RewardValuation]:
    taxed_rewards: list[RewardValuation] = []
    cumulative_base = profile.starting_taxable_base
    cumulative_tax = _tax_for_base(cumulative_base, profile)

    for reward in rewards:
        taxable_value = _select_taxable_value(reward, profile.taxable_basis)
        next_base = cumulative_base + taxable_value
        next_tax = _tax_for_base(next_base, profile)
        event_tax = next_tax - cumulative_tax
        event_rate = quantize_rate(event_tax / taxable_value) if taxable_value else Decimal("0")
        taxed_rewards.append(
            replace(
                reward,
                taxable_value=taxable_value,
                estimated_tax=event_tax,
                estimated_tax_rate=event_rate,
                cumulative_taxable_base=next_base,
                tax_profile=profile.name,
                taxable_basis=profile.taxable_basis,
            )
        )
        cumulative_base = next_base
        cumulative_tax = next_tax

    return taxed_rewards


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTIZER, rounding=ROUND_HALF_UP)


def quantize_rate(value: Decimal) -> Decimal:
    return value.quantize(RATE_QUANTIZER, rounding=ROUND_HALF_UP)


def _select_taxable_value(reward: RewardValuation, basis: str) -> Decimal:
    if basis == "gross_value":
        return reward.gross_value
    if basis == "net_value":
        return reward.net_value
    if basis == "fee_value":
        return reward.fee_value
    raise ValueError(
        f"Unsupported taxable basis: {basis}. "
        "Supported values: gross_value, net_value, fee_value."
    )


def _tax_for_base(base_amount: Decimal, profile: ResolvedTaxProfile) -> Decimal:
    taxable_base = max(base_amount, Decimal("0"))

    if profile.kind == "none":
        return Decimal("0")
    if profile.kind == "flat":
        assert profile.flat_rate is not None
        return taxable_base * profile.flat_rate
    if profile.kind == "progressive":
        return _progressive_tax(taxable_base, profile.brackets)
    raise ValueError(f"Unsupported tax profile kind: {profile.kind}")


def _progressive_tax(base_amount: Decimal, brackets: tuple[TaxBracketConfig, ...]) -> Decimal:
    remaining = base_amount
    tax = Decimal("0")
    lower_bound = Decimal("0")

    for bracket in brackets:
        if remaining <= 0:
            break

        if bracket.up_to is None:
            taxable_slice = remaining
        else:
            taxable_slice = min(remaining, bracket.up_to - lower_bound)

        if taxable_slice > 0:
            tax += taxable_slice * bracket.rate
            remaining -= taxable_slice

        if bracket.up_to is not None:
            lower_bound = bracket.up_to

    return tax
