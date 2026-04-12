# Tax Profiles

`kraken-taxes` keeps tax estimation configurable on purpose. Tax treatment for crypto rewards varies by jurisdiction, by tax year, and by the type of income involved.

## Built-in Profiles

### `none`

- disables tax estimation
- still computes reward values in the target currency

### `flat`

- applies a single configured rate to the selected taxable basis
- useful for rough planning or simplified scenarios

### `progressive`

- applies user-defined brackets to the selected taxable basis
- useful for jurisdictions or scenarios not covered by a built-in profile

### `spain_irpf_savings_2025`

- intended for reward income treated as part of the Spanish IRPF savings base
- uses `gross_value` by default as the taxable basis
- uses the 2025 savings-base rate schedule:
  - 19% up to 6,000 EUR
  - 21% from 6,000.01 to 50,000 EUR
  - 23% from 50,000.01 to 200,000 EUR
  - 27% from 200,000.01 to 300,000 EUR
  - 30% above 300,000 EUR
- reports an incremental estimate based on the configured `starting_taxable_base`

## Official References

The built-in Spain profile is based on official public sources:

- Spanish Ministry of Finance, Dirección General de Tributos, `Memoria de Actividades 2024`
  - staking rewards are described as `rendimientos del capital mobiliario`
  - they are valued at market value on the day of receipt
  - they are integrated into the `base imponible del ahorro`
  - link: https://www.hacienda.gob.es/sgt/tributos/memorias/memoria-2024.pdf

- Spain's consolidated IRPF law, Ley 35/2006, article 66 and article 76
  - these define the savings-base rate schedule currently effective from 1 January 2025
  - link: https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764

## Important Caveats

- This project does not provide legal or tax advice.
- The built-in Spain profile is an estimation layer, not a substitute for a full tax return calculation.
- The built-in Spain profile assumes savings-base treatment. If you want to model another interpretation, use a custom `progressive` or `flat` profile instead of treating the built-in one as universal truth.
- The `starting_taxable_base` setting matters for progressive schedules. It lets you account for other income already occupying lower brackets for the same period.
- Jurisdiction-specific deductions, offsets, wealth tax, VAT, business-activity treatment, and regional edge cases are outside the current scope.
