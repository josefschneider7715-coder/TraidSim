# TraidSim – technische Architektur

## 1. Anwendungsschicht

- `app.py` ist der Einstiegspunkt für Streamlit. Der Wrapper ergänzt den Strategievergleich und startet anschließend die Hauptanwendung.
- `_legacy_app.py` enthält die Benutzeroberfläche, Anmeldung, Sprachumschaltung sowie die Reiter Übersicht, Hyperopt, Simulation und Dokumentation.
- `src/i18n.py` stellt deutsche, englische und russische Oberflächentexte sowie verständliche Parameternamen bereit.

## 2. Marktdaten

`src/data_provider.py` lädt Aktienkurse über Yahoo Finance und unterstützte Kryptowährungen über Binance. Die Daten werden in ein gemeinsames OHLCV-Format mit Datum, Eröffnung, Hoch, Tief, Schlusskurs und Volumen überführt. Dadurch arbeiten alle nachfolgenden Komponenten unabhängig vom Datenanbieter mit derselben Tabellenstruktur.

## 3. Indikatoren und Strategieparameter

`src/indicators.py` berechnet SMA, RSI, MACD, Bollinger-Bänder, Fibonacci-Level, Volumendurchschnitt, Stochastik, ATR und Ichimoku. Sämtliche Perioden und Schwellen werden über `IndicatorParameters` und `StrategyParameters` übergeben. Hyperopt und Simulation verwenden damit dieselben Berechnungsfunktionen und Parameterdefinitionen.

## 4. Signal-Engine

`src/strategy.py` und `src/telemetry.py` prüfen die aktivierten Kriterien. Ein Einstieg entsteht nur, wenn alle ausgewählten technischen Kriterien erfüllt sind. Das Risikomanagement ist kein Kursfilter, sondern steuert Positionsgröße, Stop-Loss und Take-Profit. Ausstiegssignale entstehen unter anderem durch MACD-, Trend- oder RSI-Bedingungen.

## 5. Backtest und Kennzahlen

`src/backtest.py` verarbeitet die Signale chronologisch und simuliert Käufe, Verkäufe, Gebühren, ATR-Stop-Loss und ATR-Take-Profit. Daraus entstehen Trade-Liste, Kapitalverlauf, Gesamtrendite, Drawdown, Trefferquote, Anzahl abgeschlossener Trades und Endkapital. Die Simulation und Hyperopt greifen auf dieselbe Backtest-Funktion zurück.

## 6. Hyperopt

`src/hyperopt2.py` erzeugt Parameter- und Kriterienkombinationen, führt für jede Kombination Indikatorberechnung, Signalbildung und Backtest aus und bewertet das Ergebnis anhand des gewählten Ziels. Unterstützt werden maximale Rendite, minimaler Drawdown, maximale Trefferquote, risikoadjustierte Bewertung und eine ausgewogene Zielfunktion. Zusätzlich werden Konvergenz, Parameter-Importance, Heatmap, Sensitivität und Stabilitätsindex berechnet.

## 7. Simulation und Kriterien-Telemetrie

Die Simulation erlaubt das gezielte Ein- und Ausschalten aller neun technischen Kriterien sowie des Risikomanagements. `src/telemetry.py` protokolliert, wie häufig Kriterien erfüllt, blockierend, unterstützend oder entscheidend waren. Daraus entstehen Ranglisten sowie Wochen- und Monatsauswertungen. Eine Hyperopt-Empfehlung kann vollständig in die Simulation übertragen werden.

## 8. Vergleich und Robustheit

- `src/comparison.py` vergleicht Strategie, Buy-and-Hold und ein nur zur Einordnung bestimmtes Oracle.
- `src/monte_carlo.py` erzeugt mögliche Zukunftspfade aus historischen Renditen und prüft die Robustheit der Strategie.
- Das Oracle ist eine theoretische Obergrenze und fließt niemals in normale Signale oder die Optimierung ein.

## 9. Speicherung und Anmeldung

`src/storage.py` speichert Watchlists, Signalhistorie und Alarme in `app_data.db` über SQLite. Zugangsdaten liegen ausschließlich in Streamlit-Secrets und werden nicht im Repository gespeichert. Der Anmeldestatus und aktuelle UI-Auswahlen werden in der Streamlit-Session verwaltet.

## 10. Visualisierung und Deployment

Streamlit rendert Formulare, Tabellen und Navigation; Plotly erzeugt Kurs-, Kapital-, Konvergenz-, Heatmap- und Sensitivitätsdiagramme. GitHub `main` ist die veröffentlichte Codebasis. Streamlit Community Cloud erkennt neue Commits, installiert die Abhängigkeiten und startet `app.py` unter `https://traisim.streamlit.app/` neu.

## Gesamter Datenfluss

Marktdaten → Normalisierung → Indikatoren → Kriterienprüfung → Ein-/Ausstiegssignale → Backtest → Kennzahlen → Hyperopt/Simulation/Robustheit → Tabellen und Diagramme.

## Sicherheits- und Qualitätsregeln

- Zugangsdaten und Passwort-Hashes werden nicht in GitHub gespeichert.
- Das Oracle beeinflusst weder Signalbildung noch Optimierung.
- Parameter werden für Berechnung und Anzeige eindeutig benannt und typisiert.
- Änderungen werden kompiliert und durch automatisierte Tests geprüft, bevor sie veröffentlicht werden.
