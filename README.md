# Strategie-Web-App für Aktien & Krypto

Lokales Analyse- und Backtesting-Tool für Aktien, ETFs, Indizes und Kryptowährungen.

## Funktionen

- Watchlist analysieren
- Kursdaten automatisch laden
- technische Indikatoren berechnen
- Strategie-Signale ausgeben
- Backtest ausführen
- Charts anzeigen
- Trade-Liste exportieren
- Ranking nach Strategie-Score

## Installation

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Pakete installieren:

```bash
pip install -r requirements.txt
```

Start:

```bash
streamlit run app.py
```

## Beispiel-Watchlist

```text
AMZN,NVDA,MSFT,GOOGL,BTC-USD,ETH-USD,SOL-USD,1211.HK
```

## Hinweis

Dies ist keine Anlageberatung und kein Trading-Bot. Die App dient nur zur technischen Analyse und zum Backtesting.
