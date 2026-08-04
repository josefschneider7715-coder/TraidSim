# TraidSim Architektur

## Aufbau

- `app.py`: Einstiegspunkt und zusätzliche Integrationen.
- `_legacy_app.py`: bestehende Streamlit-Hauptanwendung mit Login, Übersicht, Hyperopt und Simulation.
- `src/data_provider.py`: Kursdatenbeschaffung.
- `src/indicators.py`: technische Indikatoren.
- `src/strategy.py`: klassische Signalregeln.
- `src/scored_signals.py`: Einstieg nach Trend plus Mindestzahl von Bestätigungen.
- `src/backtest.py`: Handelsausführung und Kennzahlen.
- `src/hyperopt.py`: bisherige Hyperopt-Engine.
- `src/monte_carlo.py`: Robustheitstest über simulierte Zukunftspfade.
- `src/comparison.py`: Strategie-, Buy-and-Hold- und Oracle-Vergleich.
- `src/telemetry.py`: Auswertung der Kriterien.
- `docs/`: dauerhaft versionierte Projektdokumentation.

## Datenfluss

1. Kursdaten werden geladen.
2. Indikatoren werden berechnet.
3. Signale werden erzeugt.
4. Der Backtest verarbeitet Signale am folgenden Handelstag.
5. Kennzahlen und Kapitalverläufe werden berechnet.
6. Hyperopt, Monte Carlo und Strategievergleich nutzen denselben Datenbestand mit jeweils eigener Zielsetzung.

## Sicherheitsregeln

- Zugangsdaten bleiben in `.streamlit/secrets.toml` und werden nicht in GitHub gespeichert.
- Das Oracle darf nicht in normale Signal- oder Optimierungslogik einfließen.
- Änderungen werden zuerst auf einer Branch entwickelt.
- Eine Funktion gilt erst als fertig, wenn Code, Test, Dokumentation und Übernahme in `main` abgeschlossen sind.
