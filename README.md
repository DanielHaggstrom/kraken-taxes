# Kraken Taxes

`kraken-taxes` consolidates Kraken ledger CSV exports and estimates the taxable value of reward events in a target currency using historical market data from Kraken.

The current implementation is especially useful for `earn/reward` flows such as ETH staking rewards, while preserving the full ledger history for traceability and later analysis.

## Features

- Load multiple Kraken ledger CSV exports from a directory
- Merge overlapping exports and deduplicate repeated rows
- Normalize asset codes such as `XXBT` -> `BTC` and `EUR.HOLD` -> `EUR`
- Keep source-level traceability with original file name and line number
- Value each `earn/reward` event at the event timestamp in a configurable target currency
- Use Kraken public market data to resolve direct and multi-hop conversion routes
- Cache historical price lookups locally to reduce repeated API calls
- Export both a merged ledger and a reward valuation report

## Current Scope

This project currently focuses on:

- importing Kraken ledger exports
- identifying `earn/reward` entries
- valuing those rewards in a target fiat or crypto currency available through Kraken markets

Other ledger event types such as transfers, allocations, or internal wallet movements are preserved in the merged ledger, but are not yet interpreted as taxable events by the reporting command.

## How Pricing Works

Price discovery is based on Kraken public endpoints:

- `AssetPairs` is used to discover available trading pairs
- `Trades` is used to locate historical trades near the event timestamp

For each reward event, the tool:

1. finds a conversion route from the reward asset to the target currency
2. queries historical Kraken trades near the event timestamp for each route step
3. uses the closest trade price to estimate the event value
4. computes gross, fee, and net values in the target currency

This keeps pricing aligned with Kraken market data instead of relying on daily candles or third-party aggregators.

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
```

## Commands

Show a summary of the consolidated ledger:

```powershell
python -m kraken_taxes summary
```

Export a merged, deduplicated ledger:

```powershell
python -m kraken_taxes merge --output exports/merged-ledger.csv
```

Value reward events for a specific asset and year:

```powershell
python -m kraken_taxes rewards --asset ETH --year 2025 --output reports/eth-rewards-2025.csv
```

Value all detected reward events:

```powershell
python -m kraken_taxes rewards --output reports/all-rewards.csv
```

## Report Output

The reward report includes:

- event timestamps in UTC and local output timezone
- original asset amounts: gross, fee, and net
- resolved conversion route
- effective exchange rate into the target currency
- gross, fee, and net values in the target currency
- trade timestamps used for valuation
- original `txid`, `refid`, wallet, source file, and source line

## Development

Run the test suite with:

```powershell
python -m unittest discover -s tests -v
```

## Limitations

- This project is a technical aid for recordkeeping and estimation, not tax or legal advice.
- Valuation quality depends on Kraken having sufficiently close market trades for the relevant pair.
- If no route exists from an asset to the target currency within the configured hop limit, the valuation command will fail explicitly.
- Historical valuation currently centers on `earn/reward` entries rather than a full tax-lot engine for all ledger activity.

## Roadmap Ideas

- richer handling of staking-related flows beyond reward valuation
- configurable tax-event classification rules
- support for additional market data providers
- yearly summaries and country-specific reporting layers
