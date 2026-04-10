# Kraken Taxes

Herramienta para consolidar exports de `ledger` de Kraken, deduplicarlos y calcular el valor fiscal de recompensas `earn/reward` en una divisa objetivo, con foco especial en staking de ETH y valoración en EUR.

## Qué hace

- Descubre todos los CSV de una carpeta de movimientos de Kraken.
- Fusiona exports solapados y elimina duplicados.
- Mantiene trazabilidad por `txid`, fichero y línea de origen.
- Calcula el valor bruto, la comisión y el valor neto de cada recompensa.
- Usa la API pública de Kraken para buscar trades históricos cercanos al instante del evento.
- Resuelve rutas directas o en varios saltos hacia la divisa objetivo.
- Guarda una caché local de precios para no repetir llamadas.

## Por qué Kraken como proveedor de precios

Sí, tiene sentido usar Kraken si el proyecto está centrado en Kraken. La implementación usa:

- `AssetPairs` para descubrir mercados disponibles y construir rutas de conversión.
- `Trades` para obtener trades históricos reales cerca del timestamp de la recompensa.

Nota importante:
El endpoint de `OHLC` de Kraken solo mantiene una ventana limitada para granularidades intradía, así que aquí se usa `Trades`, que permite pedir histórico desde un `since` concreto y da una valoración más precisa para eventos como recompensas de staking.

## Configuración local

El proyecto espera un fichero local ignorado por git en `config/local.toml`.

Puedes partir de `config/example.toml`:

```toml
[inputs]
ledger_dir = "C:/ruta/a/tus/movimientos"
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

## Instalación

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

## Uso

Resumen del ledger consolidado:

```powershell
python -m kraken_taxes summary
```

Exportar un ledger fusionado y deduplicado:

```powershell
python -m kraken_taxes merge --output exports/merged-ledger.csv
```

Valorar recompensas de ETH en EUR para un año concreto:

```powershell
python -m kraken_taxes rewards --asset ETH --year 2025 --output reports/eth-rewards-2025.csv
```

Valorar todas las recompensas disponibles:

```powershell
python -m kraken_taxes rewards --output reports/all-rewards.csv
```

## Salida del reporte de recompensas

Cada fila del CSV incluye:

- timestamp UTC y local
- activo
- importe bruto, comisión y neto en el activo original
- cambio usado hacia la divisa objetivo
- valor bruto, comisión y valor neto en la divisa objetivo
- ruta de conversión usada
- timestamps de los trades empleados
- `txid`, `refid`, wallet y fichero fuente

## Alcance y límites

- El cálculo está pensado como soporte técnico y trazabilidad, no como asesoramiento fiscal.
- Si un activo no tiene ruta razonable hasta la divisa objetivo dentro de Kraken, el comando fallará con un mensaje explícito.
- La precisión depende de que Kraken tenga trades suficientemente cercanos al instante del evento para el mercado relevante.
