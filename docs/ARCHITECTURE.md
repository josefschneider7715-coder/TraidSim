# Architektur

## MVP

```text
Streamlit UI
    ↓
strategy_core.py
    ↓
yfinance
```

## Spätere Zielarchitektur

```text
Browser / Frontend
    ↓
FastAPI Backend
    ↓
Strategy Engine
    ↓
Market Data Provider
    ↓
PostgreSQL
```

## Module

- `data_provider.py`: Kursdaten
- `indicators.py`: technische Indikatoren
- `strategy.py`: Signallogik
- `backtest.py`: Backtesting
- `scoring.py`: Ranking
- `charts.py`: Plotly-Charts
- `storage.py`: SQLite/PostgreSQL

## Datenmodell später

### watchlists

- id
- name
- created_at

### watchlist_items

- id
- watchlist_id
- symbol
- asset_type

### signal_history

- id
- symbol
- date
- close
- signal
- score
- rsi
- macd_status
- trend_status
- volume_status
