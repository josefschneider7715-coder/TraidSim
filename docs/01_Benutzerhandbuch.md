# DayTrade Lab Benutzerhandbuch

## Zweck

DayTrade Lab ist ein technisches Analyse- und Backtesting-Werkzeug. Es vergleicht regelbasierte Handelsstrategien mit Buy and Hold und einem theoretischen Oracle. Die Anwendung stellt keine Anlageberatung dar.

## Grundablauf

1. Watchlist oder Symbol auswählen.
2. Zeitraum, Intervall, Startkapital und Gebühren festlegen.
3. In der Übersicht den Markt und die bestehende Strategie prüfen.
4. In Hyperopt Parameterkombinationen testen.
5. In Simulation Kriterien und Zeitfenster auswählen.
6. Monte Carlo zur Robustheitsprüfung starten.
7. Strategie, Buy and Hold und Oracle vergleichen.

## Hauptreiter

### Übersicht

Zeigt Kurschart, technische Kriterien, Watchlist-Ranking, Backtest-Kennzahlen und Trades.

### Hyperopt

Testet viele Parameterkombinationen im gewählten historischen Zeitfenster. Die beste Kombination ist nur die beste der getesteten Kombinationen und keine Zukunftsgarantie.

### Simulation

Verwendet das frei gewählte Zeitfenster und die aktivierten Kriterien. Der Einstieg erfordert den Trendfilter, sofern aktiviert, sowie mindestens drei weitere Bestätigungen.

### Dokumentation

Enthält Bedienung, Architektur, Roadmap, Changelog und Ideenübersicht direkt in DayTrade Lab.

## Wichtige Kennzahlen

- Gesamtrendite: Veränderung des Kapitals vom Start bis zum Ende.
- Maximaler Drawdown: größter zwischenzeitlicher Rückgang vom vorherigen Kapitalhoch.
- Trefferquote: Anteil profitabler abgeschlossener Trades.
- Marktzeit: Anteil des Zeitraums, in dem Kapital investiert war.
- Signalvorteil: Differenz zwischen der Strategie mit 100 Prozent Kapitaleinsatz und Buy and Hold.

## Methodische Grenzen

- Historische Ergebnisse sind keine Prognosegarantie.
- Hyperopt kann überoptimieren.
- Das Oracle verwendet vollständiges Zukunftswissen und ist nicht handelbar.
- Gebühren, Ausführungskurse und Datenqualität beeinflussen das Ergebnis erheblich.
