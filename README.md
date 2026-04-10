# Kraken Taxes

`kraken-taxes` consolidates Kraken ledger CSV exports and estimates the value and tax impact of reward events using historical Kraken market data.

It is built for people who want a reproducible, inspectable workflow for reward-based crypto income, especially Kraken `earn/reward` entries such as staking rewards.

## What It Does

- loads multiple Kraken ledger CSV exports from a directory
- merges overlapping exports and deduplicates repeated rows
- normalizes Kraken asset codes such as `XXBT` -> `BTC` and `EUR.HOLD` -> `EUR`
- values each `earn/reward` event at the event timestamp in a configurable target currency
- resolves direct and multi-hop conversion routes using Kraken public markets
- caches historical quote lookups locally to reduce repeated API calls
- estimates taxes with configurable tax profiles
- exports both machine-friendly CSV and human-friendly HTML reports

## Current Scope

Today the project focuses on reward-income workflows:

- import Kraken ledger exports
- identify `earn/reward` entries
- estimate value at receipt
- estimate tax using a configurable profile

Other ledger events such as transfers, allocations, or wallet movements are preserved in the merged ledger for traceability, but are not yet treated as full tax-lot events.

## Pricing Model

Historical pricing uses Kraken public endpoints:

- `AssetPairs` to discover available conversion routes
- `Trades` to find market trades near the reward timestamp

For each reward event the tool:

1. finds a route from the reward asset to the target currency
2. queries historical Kraken trades near the event timestamp for each route step
3. uses the closest trade price for each step
4. computes gross, fee, and net value in the target currency

This keeps valuation tied to Kraken market data rather than daily candles or third-party aggregators.

## Tax Estimation

Tax estimation is configurable. The project currently ships with:

- `none`
- `flat`
- `progressive`
- `spain_irpf_savings_2025`

The built-in Spain profile is intended for reward income treated as part of the IRPF savings base. See [docs/tax-profiles.md](docs/tax-profiles.md) for details and official references.

Important:

- tax estimation is a planning and recordkeeping aid, not tax advice
- the correct treatment depends on jurisdiction, tax year, and facts not always present in a ledger export
- progressive estimates can be materially wrong if you do not configure the starting taxable base for the period

## Installation

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

## Configuration

Runtime configuration is loaded from `config/local.toml`. This file is intentionally ignored by git so local paths and preferences stay private.

Start by copying `config/example.toml` to `config/local.toml` and adjusting the values:

```toml
[inputs]
ledger_dir = "C:/path/to/kraken/ledger/exports"
ledger_glob = "*.csv"

[project]
target_currency = "EUR"
source_timezone = "UTC"
output_timezone = "Europe/Madrid"

[pricing]
provider = "kraken"
price_cache_path = ".cache/kraken_price_cache.json"
initial_trade_window_seconds = 300
max_trade_window_seconds = 86400
route_max_hops = 2
preferred_intermediates = ["EUR", "USD", "USDT", "USDC", "BTC", "ETH"]
http_timeout_seconds = 20

[tax]
profile = "spain_irpf_savings_2025"
starting_taxable_base = "0"
```

### Key Tax Settings

- `profile`
  Selects the tax model to use.

- `starting_taxable_base`
  Lets you account for other income already occupying part of the same tax brackets for the selected period.

- `taxable_basis`
  Available for custom `flat` or `progressive` profiles. Supported values are `gross_value`, `net_value`, and `fee_value`.

## Commands

Show a summary of the consolidated ledger:

```powershell
python -m kraken_taxes summary
```

Export a merged, deduplicated ledger:

```powershell
python -m kraken_taxes merge --output exports/merged-ledger.csv
```

Value reward events and print a console summary:

```powershell
python -m kraken_taxes rewards --asset ETH --year 2025 --output reports/eth-rewards-2025.csv
```

Generate a complete CSV + HTML report:

```powershell
python -m kraken_taxes report --asset ETH --year 2025 --csv-output reports/eth-2025.csv --html-output reports/eth-2025.html
```

## CSV Output

The detailed reward CSV includes:

- event timestamps in UTC and local output timezone
- gross, fee, and net amounts in the original asset
- effective exchange rate into the target currency
- gross, fee, and net values in the target currency
- taxable value and estimated tax
- cumulative taxable base used by the estimator
- conversion route and trade timestamps used for valuation
- original `txid`, `refid`, wallet, source file, and source line

## HTML Report

The HTML report is intended for review and recordkeeping. It includes:

- headline totals
- selected tax profile and assumptions
- cache and runtime context
- summary by asset
- monthly progression
- detailed reward-event table

## Development

Run the test suite with:

```powershell
python -m unittest discover -s tests -v
```

## Limitations

- This project does not replace professional tax or legal advice.
- Valuation quality depends on Kraken having sufficiently close market trades for the relevant pair.
- If no route exists from an asset to the target currency within the configured hop limit, valuation fails explicitly.
- The current tax layer focuses on reward-income estimation, not a full disposal / tax-lot engine.

## Roadmap

- broader treatment of staking-related flows beyond reward receipt
- disposal tracking and tax-lot support
- additional market-data providers
- more built-in jurisdiction profiles
- richer yearly summaries and export formats
