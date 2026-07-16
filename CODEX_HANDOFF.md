# CODEX HANDOFF – Strategie-Web-App für Aktien & Krypto

## Ziel

Baue aus diesem Projekt eine lokale bzw. später serverfähige Web-App zur technischen Analyse, Watchlist-Prüfung und zum Backtesting einer definierten Trading-Strategie.

Die App soll:

- Aktien, ETFs, Indizes und Kryptowährungen laden
- Charts darstellen
- technische Indikatoren berechnen
- die definierte Strategie prüfen
- Kauf-/Warte-/Halte-/Verkaufssignale anzeigen
- Backtests ausführen
- Watchlist-Ranking erstellen
- Ergebnisse exportieren
- später als Web-App mit Login und automatischen Benachrichtigungen laufen

Wichtig: Die App ist ein Analyse- und Backtesting-Werkzeug. Sie ist kein Broker, kein Trading-Bot und keine Anlageberatung.

---

## Aktueller Projektstand

Dieses Paket enthält einen lauffähigen MVP-Startpunkt mit:

- Streamlit-Weboberfläche
- yfinance-Datenquelle
- Strategie-Modul
- Indikatoren:
  - SMA 20
  - SMA 50
  - SMA 200
  - RSI 14 nach Wilder
  - MACD 12/26/9
  - Bollinger-Bänder 20/2
  - ATR 14 nach Wilder
  - Volumen-SMA 20
- Watchlist-Analyse
- Signal-Score
- einfacher Long-only Backtest
- Plotly-Charts
- CSV-Export

---

## Gewünschter technischer Stack

Für den MVP:

- Python 3.11+
- Streamlit
- pandas
- numpy
- plotly
- yfinance

Späterer Ausbau:

- FastAPI Backend
- React oder Next.js Frontend
- PostgreSQL
- Redis/Celery oder APScheduler für automatische Scans
- Authentifizierung
- Docker
- Deployment auf Hetzner VPS

---

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

App starten:

```bash
streamlit run app.py
```

---

## Beispiel-Watchlist

```text
AMZN,NVDA,MSFT,GOOGL,META,TSLA,BTC-USD,ETH-USD,SOL-USD,1211.HK,^GDAXI
```

---

## Strategie-Regeln

### Einstieg Long

Ein Einstieg ist nur erlaubt, wenn alle harten Bedingungen erfüllt sind:

1. Kurs > SMA 200
2. SMA 50 > SMA 200
3. Kurs > SMA 50
4. Kurs > Bollinger-Mitte
5. RSI zwischen 40 und 65
6. MACD > MACD-Signal
7. Volumen > Volumen-SMA 20

Zusätzlich kann später eine strengere Variante eingebaut werden:

- RSI kreuzt von unten über 40
- MACD kreuzt frisch bullisch
- Tagesschluss über relevantem Widerstand
- relative Stärke gegenüber Benchmark positiv

### Ausstieg

Ausstieg bei:

1. Kurs < SMA 50
2. MACD < MACD-Signal
3. RSI > 75
4. ATR-Stop-Loss erreicht
5. ATR-Take-Profit erreicht

### Risiko-Management

- Risiko pro Trade Standard: 1 %
- Stop-Loss: Einstiegspreis - 2 × ATR
- Take-Profit: Einstiegspreis + 3 × ATR
- Keine Hebel
- Keine Shorts im MVP
- Keine automatische Orderausführung

---

## Signal-Kategorien

Die App soll diese Signalstufen ausgeben:

- `KAUF`
- `BEOBACHTEN / FAST SETUP`
- `HALTEN`
- `WARNUNG / WARTEN`
- `KEIN TRADE / TREND NEGATIV`
- `VERKAUF / AUSSTIEG`

Für die erste MVP-Version reichen:

- `KAUF`
- `BEOBACHTEN / FAST SETUP`
- `WARNUNG / WARTEN`
- `KEIN TRADE / TREND NEGATIV`

---

## Backtest-Anforderungen

Der Backtest soll mindestens ausgeben:

- Startkapital
- Endkapital
- Gesamtrendite %
- maximale Drawdown %
- Anzahl abgeschlossener Trades
- Trefferquote %
- Gesamtgewinn
- Durchschnitt pro Trade
- bester Trade
- schlechtester Trade
- Trade-Liste mit Datum, Kauf, Verkauf, Preis, Stückzahl, Gewinn/Verlust und Grund

Später ergänzen:

- Vergleich gegen Buy-and-Hold
- CAGR
- Sharpe Ratio
- Sortino Ratio
- Profit Factor
- Exposure Time
- monatliche Renditen
- Monte-Carlo-Simulation
- Walk-forward-Test
- Parameter-Optimierung

---

## UI-Anforderungen

Die Web-App soll enthalten:

### Sidebar

- Watchlist-Eingabe
- Zeitraum
- Intervall
- Startkapital
- Risiko pro Trade
- Gebühr pro Order
- ATR-Stop-Faktor
- ATR-Take-Profit-Faktor
- Analyse starten

### Hauptbereich

1. Watchlist-Ranking
2. Detailauswahl eines Symbols
3. Signal-Karte
4. Kriterienprüfung
5. Kurschart mit Candlesticks, SMA und Bollinger
6. RSI-Chart
7. MACD-Chart
8. Volumen-Chart
9. Backtest-Kennzahlen
10. Equity-Curve
11. Trade-Tabelle
12. CSV-Downloads

---

## Rechtlicher Hinweis

In der App muss sichtbar stehen:

> Dies ist ein technisches Analyse- und Backtesting-Tool. Es handelt sich nicht um Anlageberatung. Die Signale sind regelbasierte technische Auswertungen und keine persönliche Kauf- oder Verkaufsempfehlung.

---

## Wichtige Codex-Aufgaben

### Aufgabe 1 – Projekt lauffähig machen

Prüfe das Projekt, installiere Requirements und starte:

```bash
streamlit run app.py
```

Behebe Importfehler, Darstellungsfehler oder yfinance-Probleme.

### Aufgabe 2 – Struktur verbessern

Zielstruktur:

```text
strategy_web_app/
├── app.py
├── requirements.txt
├── README.md
├── CODEX_HANDOFF.md
├── src/
│   ├── __init__.py
│   ├── data_provider.py
│   ├── indicators.py
│   ├── strategy.py
│   ├── backtest.py
│   ├── scoring.py
│   └── charts.py
├── docs/
│   ├── PRODUCT_SPEC.md
│   ├── ARCHITECTURE.md
│   └── ROADMAP.md
└── tests/
    ├── test_indicators.py
    ├── test_strategy.py
    └── test_backtest.py
```

Aktuell ist ein Teil noch zusammengefasst. Bitte modularisieren.

### Aufgabe 3 – Buy-and-Hold Vergleich einbauen

Für jedes Symbol soll zusätzlich angezeigt werden:

- Strategie-Rendite
- Buy-and-Hold-Rendite
- Differenz
- Strategie Drawdown
- Buy-and-Hold Drawdown

### Aufgabe 4 – Watchlists speichern

Baue einfache lokale Speicherung ein:

- SQLite-Datei `app_data.db`
- Tabelle `watchlists`
- Name der Watchlist
- kommaseparierte Symbole oder separate Tabelle `watchlist_items`

### Aufgabe 5 – Signal-Historie speichern

Speichere täglich:

- Datum
- Symbol
- Kurs
- Signal
- Score
- RSI
- MACD-Status
- SMA-Status
- Volumenstatus

### Aufgabe 6 – Alarmfunktion vorbereiten

Noch keine echten E-Mails nötig. Erst:

- Tabelle `alerts`
- Wenn Signal `KAUF`, dann Eintrag erzeugen
- Anzeige in UI: „Neue Signale“

Später:

- Telegram Bot
- E-Mail
- Push-Benachrichtigung

### Aufgabe 7 – Datenquelle abstrahieren

`yfinance` soll nur eine Datenquelle sein. Baue Interface:

```python
class MarketDataProvider:
    def get_history(symbol, period, interval) -> pd.DataFrame:
        ...
```

Später sollen möglich sein:

- yfinance
- Alpha Vantage
- Polygon.io
- Twelve Data
- Binance für Krypto

### Aufgabe 8 – Tests ergänzen

Mindestens:

- SMA korrekt
- RSI Wertebereich 0–100
- MACD Spalten vorhanden
- Entry-Signal nur bei erfüllten Kriterien
- Backtest erzeugt Equity-Kurve
- keine NaN-Probleme am Ende

### Aufgabe 9 – Docker vorbereiten

Erstelle später:

```text
Dockerfile
docker-compose.yml
```

Für Serverbetrieb auf Hetzner.

### Aufgabe 10 – Benutzerlogin später

Nicht im MVP nötig. Später:

- Authentifizierung
- Benutzer-Watchlists
- Datenbank pro Benutzer
- HTTPS über Reverse Proxy

---

## Coding Style

- Typannotationen verwenden
- Funktionen klein halten
- Keine Broker-Orderausführung
- Fehler im UI klar anzeigen
- Keine stillen Exceptions
- CSV-Export beibehalten
- Strategieparameter zentral konfigurierbar machen
- Keine sensiblen API-Keys im Code speichern

---

## Definition of Done für MVP

MVP ist fertig, wenn:

- App startet ohne Fehler
- Watchlist kann analysiert werden
- für jedes Symbol wird ein Score berechnet
- Detailchart funktioniert
- Kauf-/Verkaufssignale werden im Chart markiert
- Backtest-Kennzahlen werden angezeigt
- Trade-Tabelle wird angezeigt
- CSV-Export funktioniert
- rechtlicher Hinweis ist sichtbar

---

## Wichtig für Codex

Bitte nicht direkt einen Trading-Bot bauen. Erst Analyse-Tool stabil machen.

Priorität:

1. Stabilität
2. korrekte Indikatoren
3. nachvollziehbare Signale
4. gute Charts
5. saubere Backtests
6. Speicherung
7. Automatisierung
8. Deployment
