from __future__ import annotations


DOCUMENTATION = {
    "de": r"""
# TraidSim – Benutzer- und Systemhandbuch

TraidSim ist eine technische Analyse-, Backtesting- und Optimierungsanwendung für Aktien und Kryptowährungen. Die Anwendung verbindet historische Marktdaten, technische Indikatoren, regelbasierte Kriterien, Risikomanagement, Backtests, Hyperopt und Robustheitsauswertungen. Sie liefert technische Simulationen, aber keine Anlageberatung.

## 1. Empfohlener Arbeitsablauf

1. Links in den **Einstellungen** Watchlist, Zeitraum, Intervall, Kapital, Gebühren und Risikowerte festlegen.
2. In der **Übersicht** Datenqualität, aktuelles Signal, Strategie-Score, Kurschart und bisherigen Backtest prüfen.
3. In **Hyperopt** ein Optimierungsziel wählen, alle zulässigen Kriterien aktivieren und die Optimierung starten.
4. Konvergenz, Stabilität, Rendite, Drawdown und empfohlene Konfiguration gemeinsam beurteilen.
5. Mit **Empfehlung vollständig in Simulation übernehmen** Kriterien, Parameter und Risikomanagement übertragen.
6. In der **Simulation** denselben Zeitraum kontrollieren und Ergebnis, Ranglisten, Ereignisse und Robustheit prüfen.

## 2. Anmeldung, Sprache und Sitzung

Das Login schützt die Anwendung vor unberechtigtem Zugriff. Benutzer und Passwort-Hash werden über Streamlit-Secrets bereitgestellt und nicht im GitHub-Repository gespeichert. Nach der Anmeldung startet die Detailansicht standardmäßig mit **AAPL**, dem Ziel **Maximale Rendite** und aktivierten Hyperopt-Kriterien. Die Flagge oben rechts wechselt Deutsch, Englisch und Russisch. Eingaben werden während der laufenden Streamlit-Sitzung im Session-State gehalten.

## 3. Einstellungen in der linken Seitenleiste

### Gespeicherte Watchlist
Wählt eine zuvor in SQLite gespeicherte Symbolgruppe. **Manuelle Eingabe** verwendet den Inhalt des darunterliegenden Textfelds.

### Watchlist, getrennt mit Komma
Enthält Börsensymbole wie `AAPL`, `AMZN`, `NVDA`, `BTC-USDT` oder `1211.HK`. Ungültige oder nicht erreichbare Symbole erscheinen in der Fehlerübersicht.

### Watchlist speichern als / Watchlist speichern
Vergibt einen Namen und speichert die aktuelle Symbolliste. Bereits vorhandene Namen werden aktualisiert.

### Zeitraum
Bestimmt die historische Datenmenge, beispielsweise sechs Monate, ein Jahr, fünf Jahre oder maximal verfügbar. Lange Indikatoren wie SMA 200 benötigen ausreichend viele Kurszeilen.

### Intervall
Legt die Kerzengröße fest: täglich, wöchentlich oder monatlich. Parameterperioden beziehen sich immer auf Kerzen, nicht automatisch auf Kalendertage.

### Startkapital
Kapital zu Beginn des Backtests. Es beeinflusst absolute Endkapital- und Gewinnwerte, nicht unmittelbar die prozentuale Kursbewegung.

### Risiko pro Trade
Anteil des Kapitals, der über Positionsgröße und Stop-Distanz riskiert wird. Intern entspricht `0,02` einem Risiko von 2 %. In der Simulation wird der Wert verständlich als Prozentwert angezeigt.

### Gebühr pro Order
Prozentuale Transaktionsgebühr für Kauf und Verkauf. Viele Trades können dadurch trotz guter Bruttosignale zu einer negativen Nettorendite führen.

### ATR Stop-Loss-Faktor
Abstand des Stop-Loss als Vielfaches der ATR. Ein kleiner Wert begrenzt Verluste früh, kann aber häufiger durch normales Marktrauschen ausgelöst werden.

### ATR Take-Profit-Faktor
Gewinnziel als Vielfaches der ATR. Große Werte erlauben längere Trends, werden jedoch seltener erreicht.

### Hyperopt-Durchläufe
Anzahl getesteter Kombinationen. Mehr Durchläufe durchsuchen den Raum gründlicher, benötigen aber mehr Rechenzeit. Ein guter Einzelwert ersetzt keine Out-of-sample-Prüfung.

### Hyperopt Mindest-Trades
Verwirft Konfigurationen mit zu wenigen abgeschlossenen Trades. Dadurch sollen zufällige Spitzenresultate aus einzelnen Trades vermieden werden.

### Neu berechnen
Löst einen erneuten Streamlit-Durchlauf mit den aktuellen Seitenleistenwerten aus.

## 4. Detailansicht und Reiter

**Detailansicht auswählen** bestimmt, für welches erfolgreich geladene Symbol Charts, Hyperopt und Simulation angezeigt werden. Nach der Anmeldung ist Apple (`AAPL`) vorausgewählt. Die Anwendung besitzt vier Reiter: **Übersicht**, **Hyperopt**, **Simulation** und **Dokumentation**.

## 5. Übersicht

### Strategiechart
Zeigt Kurs und technische Indikatoren. Er dient zur visuellen Kontrolle, ob Trend, Volatilität und Signale plausibel zum Kursverlauf passen.

### Signal und Strategie-Score
Das aktuelle Signal fasst die jüngste regelbasierte Bewertung zusammen. Der Score zählt erfüllte technische Prüfungen. Ein hoher Score ist keine Renditeprognose und keine Kaufempfehlung.

### Kriterienprüfung
Listet pro Kriterium, ob es in der jüngsten Kerze erfüllt ist. So lässt sich nachvollziehen, warum ein Signal entstand oder blockiert wurde.

### Watchlist-Ranking
Vergleicht Symbole anhand Strategieergebnis, Buy-and-Hold, Drawdown, Trefferquote und weiteren Kennzahlen. Unterschiedliche Datenlängen oder Märkte müssen bei der Interpretation berücksichtigt werden.

### Backtest-Kennzahlen und Trades
Der Backtest zeigt Gesamtrendite, Endkapital, Drawdown, Trefferquote, abgeschlossene Trades und Gewinnsummen. Die Trade-Tabelle enthält chronologische Käufe und Verkäufe. CSV-Buttons exportieren Ranking und Trades.

## 6. Hyperopt – Eingaben und Buttons

### Optimierungsziel
- **Maximale Rendite:** bevorzugt die höchste historische Gesamtrendite; erhöhtes Risiko kann dabei dominant werden.
- **Minimaler Drawdown:** bevorzugt geringe Kapitalrückgänge und bestraft negative Rendite.
- **Maximale Trefferquote:** bevorzugt einen hohen Anteil profitabler Trades, berücksichtigt Rendite aber nur ergänzend.
- **Risikoadjustiert:** setzt Rendite ins Verhältnis zum Drawdown.
- **Ausgewogen:** kombiniert Rendite, Drawdown und Trefferquote.

### Kriterienauswahl
Die Häkchen legen den Suchraum fest. Hyperopt darf aus aktivierten technischen Kriterien unterschiedliche Kombinationen testen. Das Häkchen **Risikomanagement** erlaubt zusätzlich die Optimierung von Risiko, Stop-Loss und Take-Profit.

### Hyperopt starten
Erzeugt Parameter- und Kriterienkombinationen. Jeder Durchlauf berechnet Indikatoren neu, erzeugt Signale, führt denselben Backtest wie die Simulation aus und bewertet das Resultat mit dem gewählten Objective.

## 7. Die zehn Kriterien

1. **Trend:** Kurs und Trend-SMA müssen oberhalb des langfristigen SMA 200 liegen. Parameter: Trend-SMA-Periode.
2. **RSI:** RSI muss innerhalb der unteren und oberen Einstiegsschwelle liegen. Zusätzlich existiert eine RSI-Ausstiegsschwelle.
3. **MACD:** MACD-Linie muss oberhalb ihrer Signallinie liegen. Parameter: schnelle EMA, langsame EMA und Signal-EMA.
4. **Bollinger:** Der Kurs muss oberhalb der mittleren Bollinger-Linie liegen. Parameter: Berechnungsperiode und Standardabweichung.
5. **Fibonacci:** Der Kurs muss die berechnete 61,8-%-Unterstützung halten. Parameter: Rückblickperiode.
6. **Volumen:** Aktuelles Volumen muss den gleitenden Volumendurchschnitt multipliziert mit dem Mindestfaktor überschreiten.
7. **Stochastik:** %K muss zwischen unterer und oberer Schwelle sowie oberhalb von %D liegen. Parameter: Periode, %D-Glättung und Grenzwerte.
8. **ATR:** Die ATR-Volatilität in Prozent muss innerhalb des erlaubten Bereichs liegen. Parameter: ATR-Periode, Minimum und Maximum.
9. **Ichimoku:** Kurs muss über der Wolke und Tenkan über Kijun liegen. Parameter: Tenkan-, Kijun- und Senkou-B-Periode.
10. **Risikomanagement:** Kein Kursfilter. Es steuert Risiko je Trade, ATR-Stop-Loss und ATR-Take-Profit.

## 8. Hyperopt-Ergebnisse

### Rendite, Drawdown, Trades und Stabilitätsindex
Die vier Hauptkennzahlen beschreiben die beste getestete Konfiguration. Rendite allein reicht nicht: Eine Konfiguration mit hohem Drawdown, wenigen Trades oder geringer Stabilität kann überangepasst sein.

### Konvergenz
Die orange Linie zeigt den Abstand zur endgültig besten Lösung. Grüne Rauten markieren neue Bestwerte. Die gepunktete Linie zeigt den bis dahin besten Objective-Wert. Zusätzlich werden gültige und wegen Mindest-Trades bestrafte Versuche sowie der Fundzeitpunkt des endgültigen Bestwerts angezeigt. Frühe Konvergenz kann gut sein, beweist aber keine Robustheit.

### Empfohlene Kriterien
Die Ja/Nein-Tabelle ist das Ergebnis der getesteten Kriterienkombinationen. **Nein** bedeutet nur, dass dieses Kriterium im untersuchten Zeitraum und Ziel nicht Bestandteil der besten Kombination war.

### Empfohlene Parameterwerte
Zeigt ausschließlich die Werte der empfohlenen Kriterien und – sofern aktiviert – des Risikomanagements. Die Werte sind historisch optimiert und sollten nicht ungeprüft als dauerhaft gültig betrachtet werden.

### Empfehlung vollständig in Simulation übernehmen
Überträgt technische Kriterien, alle Parameterwerte, Risiko je Trade, ATR-Stop-Loss und ATR-Take-Profit in die Simulation. Zeitraum, Intervall, Startkapital und Gebühren stammen weiterhin aus den allgemeinen Einstellungen und müssen für einen exakten Vergleich identisch sein.

### Parameter-Importance
Schätzt, welche Parameter oder Kriterien die Objective-Werte im aktuellen Lauf am stärksten verändert haben. Importance ist ein Zusammenhang innerhalb der getesteten Stichprobe, keine Ursache und keine Garantie für künftige Bedeutung.

### Heatmap
Zeigt den mittleren Objective-Wert für Kombinationen der zwei wichtigsten Parameter. Grün bedeutet im aktuellen Lauf besser, Rot schlechter. Leere oder schwach belegte Zellen sind weniger belastbar.

### Sensitivität
Zeigt, wie sich der mittlere Objective-Wert mit einzelnen Parameterwerten verändert. Starke Sprünge deuten auf eine empfindliche Strategie hin; breite Plateaus sind meist robuster. Parameter mit unterschiedlichen Einheiten dürfen nicht direkt miteinander verglichen werden.

### Stabilitätsindex und KI-Auswertung
Der Stabilitätsindex bewertet Streuung, positive Ergebnisse und Drawdown der besten Versuche. Die Textauswertung fasst Stabilität und Abstand zu Buy-and-Hold zusammen. Sie ist eine regelbasierte Interpretation, keine autonome Anlageentscheidung.

### Benchmarks und CSV
**Buy-and-Hold** zeigt passives Halten. **Oracle** nutzt perfekte Zukunftskenntnis als theoretische Obergrenze und beeinflusst niemals Signale oder Hyperopt. Der CSV-Download enthält sämtliche getesteten Kombinationen und Kennzahlen.

## 9. Simulation – Eingaben und Buttons

### Zeitfenster
Start- und Enddatum begrenzen den untersuchten Abschnitt. Indikatoren werden auf der gesamten geladenen Historie aufgebaut und anschließend auf das Simulationsfenster gefiltert, damit am Start ausreichende Vorlaufdaten vorhanden sind.

### Parameter ein- und ausschalten
Die zehn Schalter entsprechen der Hyperopt-Darstellung. Alle aktivierten technischen Kriterien müssen gleichzeitig erfüllt sein. Das Risikomanagement wird separat auf Positionsgröße und Ausstiegsgrenzen angewendet.

### Werte der aktiven Kriterien einstellen
Zeigt nur Eingaben, die zu aktivierten Kriterien gehören. Jede Änderung berechnet Indikatoren, Signale, Trades und Auswertungen sofort neu. Unlogische Kombinationen – etwa eine untere Schwelle oberhalb der oberen – können alle Signale verhindern.

### Simulations-Kennzahlen
Zeigen aktive Kriterien, Zahl der Kriterienauswertungen, abgeschlossene Trades und Rendite. Darunter folgt die vollständige Backtest-Kennzahlentabelle.

## 10. Kriterien-Telemetrie und Ranglisten

- **Auswertungen:** Anzahl geprüfter Kurszeilen.
- **Erfüllt:** Wie oft das Kriterium bestanden wurde.
- **Auslöser:** Beteiligung an tatsächlichen Einstiegssignalen.
- **Blockiert:** Nahezu vollständige Setups, die durch dieses Kriterium verhindert wurden.
- **Unterstützt:** Erfüllt, ohne allein entscheidend zu sein.
- **Entscheidend:** Als Auslöser oder Blockierer besonders relevante Ereignisse.
- **Relevanzscore:** gewichtete Kombination aus Entscheidungseinfluss, Profit-, Risiko- und Stabilitätswert.
- **Bewertung:** beispielsweise hoch relevant, mittel relevant, gering relevant, negativ wirkend oder nicht ausreichend beobachtet.

Eine negative Bewertung bedeutet, dass das Kriterium im untersuchten Zeitraum ungünstig mit den Ergebnissen zusammenhing. Sie beweist nicht, dass der Indikator grundsätzlich ungeeignet ist.

### Wochen-/Monatsaggregate und Signalereignisse
Die Tabellen fassen Kriterienwerte nach Wochen und Monaten zusammen. Die Ereignistabelle macht einzelne Prüfungen und ihre späteren Kursbewegungen nachvollziehbar. Diese Ansichten helfen, ein nur in kurzen Marktphasen funktionierendes Kriterium zu erkennen.

### Monte-Carlo-Zukunftssimulation
Erzeugt viele mögliche Ein-Jahres-Pfade aus historischen Renditen und führt die Strategie darauf aus. Pfadanzahl und Zufalls-Seed steuern Umfang und Reproduzierbarkeit. Das Ergebnis ist ein Robustheitstest unter modellierten Szenarien, keine Kursprognose.

### Strategievergleich
Stellt die aktive Strategie Buy-and-Hold und Oracle gegenüber. Entscheidend sind nicht nur Rendite, sondern auch Drawdown, Anzahl der Trades, Gebühren und zeitlicher Verlauf der Kapitalkurve.

## 11. Technische Architektur

1. `app.py` startet Streamlit und integriert den Strategievergleich.
2. `_legacy_app.py` orchestriert Login, Sprache, Datenabruf und Reiter.
3. `src/data_provider.py` normalisiert Yahoo-Finance- und Binance-Daten in OHLCV.
4. `src/indicators.py` berechnet alle Indikatoren aus typisierten Parametern.
5. `src/strategy.py` und `src/telemetry.py` erzeugen und erklären Signale.
6. `src/backtest.py` simuliert Trades und berechnet Kennzahlen.
7. `src/hyperopt2.py` durchsucht Kriterien- und Parameterkombinationen.
8. `src/monte_carlo.py` prüft modellierte Zukunftspfade.
9. `src/storage.py` speichert Watchlists, Historie und Alarme in SQLite.
10. Plotly visualisiert Ergebnisse; Streamlit Community Cloud veröffentlicht GitHub `main` unter `traisim.streamlit.app`.

**Datenfluss:** Marktdaten → Normalisierung → Indikatoren → Kriterien → Signale → Backtest → Kennzahlen → Hyperopt/Simulation → Robustheit → Tabellen und Diagramme.

## 12. Grenzen und richtige Interpretation

- Historische Optimierung kann überangepasst sein.
- Ergebnisse hängen von Symbol, Zeitraum, Intervall, Gebühren und Datenqualität ab.
- Mehr Risiko kann Rendite und Drawdown gleichzeitig erhöhen.
- Wenige Trades liefern statistisch schwache Aussagen.
- Importance, Heatmap und Sensitivität sind diagnostische Hilfen, keine Zukunftsbeweise.
- Vor produktiver Verwendung sind Walk-forward-, Out-of-sample- und mehrere Marktphasen-Tests erforderlich.
""",
    "en": r"""
# TraidSim – User and system guide

TraidSim combines historical market data, technical indicators, rule-based criteria, risk management, backtesting, Hyperopt and robustness analysis. It is a technical simulation tool, not investment advice.

## 1. Recommended workflow

1. Set watchlist, period, interval, capital, fees and risk values in the sidebar.
2. Review data, current signal, score, chart and backtest in **Overview**.
3. Select an objective and allowed criteria in **Hyperopt**, then run optimization.
4. Judge return together with drawdown, trades, convergence and stability.
5. Use **Apply full recommendation to simulation**.
6. Validate the same configuration and period in **Simulation**.

## 2. Sidebar inputs

- **Saved watchlist / manual entry:** loads a stored list or comma-separated symbols.
- **Save watchlist:** writes the current list to SQLite under the selected name.
- **Period and interval:** define historical depth and candle size. Indicator periods count candles.
- **Initial capital:** starting equity for all comparisons.
- **Risk per trade:** position risk; internal `0.02` means 2%.
- **Fee per order:** applied to every buy and sell.
- **ATR stop-loss / take-profit:** volatility-based exit distances.
- **Hyperopt trials:** number of tested combinations.
- **Minimum trades:** penalizes results with too few closed trades.
- **Recalculate:** reruns the application using current values.

## 3. Overview

The strategy chart combines price and indicators. The latest signal and strategy score summarize fulfilled checks but are not forecasts. The criteria table explains the signal. Watchlist ranking compares strategy, Buy-and-Hold, drawdown and win rate. Backtest metrics and the trade table can be exported as CSV.

## 4. Hyperopt objectives and controls

- **Maximum return:** maximizes historical return and may favor greater risk.
- **Minimum drawdown:** favors smaller equity declines.
- **Maximum win rate:** favors a higher share of profitable trades.
- **Risk adjusted:** relates return to drawdown.
- **Balanced:** combines return, drawdown and win rate.

Checkboxes define which criteria Hyperopt may compare. Risk management allows optimization of risk, stop and target. **Run Hyperopt** rebuilds indicators, signals and a backtest for every combination using the same engine as Simulation.

## 5. The ten criteria

1. **Trend:** price and trend SMA above SMA 200; parameter: trend SMA period.
2. **RSI:** RSI inside lower/upper entry range; includes an exit threshold.
3. **MACD:** MACD above signal; fast, slow and signal EMA periods.
4. **Bollinger:** close above the middle band; period and standard deviation.
5. **Fibonacci:** price holds the calculated 61.8% support; lookback period.
6. **Volume:** current volume exceeds its average times a minimum factor.
7. **Stochastic:** %K inside thresholds and above %D; periods and bounds.
8. **ATR:** ATR percentage inside a tradable range; period, minimum and maximum.
9. **Ichimoku:** price above cloud and Tenkan above Kijun; three periods.
10. **Risk management:** not a price filter; controls position risk, stop and target.

## 6. Hyperopt results

- **Return, drawdown, trades, stability:** headline metrics for the best trial.
- **Convergence:** distance to the final best, new-best markers, running-best objective, valid and penalized trials, and the trial that found the winner.
- **Recommended criteria:** Yes/No composition of the best tested strategy.
- **Recommended values:** values belonging to selected criteria and risk management.
- **Apply to simulation:** transfers criteria, values, risk, ATR stop and ATR target. Period, interval, capital and fees must also match for an exact comparison.
- **Importance:** association between tested parameters and objective variation; not causality.
- **Heatmap:** average objective for combinations of the two leading parameters.
- **Sensitivity:** average objective by parameter value; sharp changes indicate fragility, broad plateaus suggest robustness.
- **Stability evaluation:** summarizes dispersion, positive outcomes and drawdown among leading trials.
- **Buy-and-Hold / Oracle:** passive benchmark and theoretical perfect-foresight upper bound. Oracle never affects signals.
- **CSV download:** exports all trials, parameters and metrics.

## 7. Simulation inputs and outputs

The date window restricts analysis while indicators retain sufficient history. Ten switches mirror Hyperopt. All enabled technical criteria must pass simultaneously; risk management acts on sizing and exits. The parameter expander shows only relevant values and recalculates indicators, signals, trades and results immediately.

Headline metrics show active criteria, evaluations, trades and return. Detailed metrics include final capital, drawdown and win rate.

## 8. Telemetry and rankings

Telemetry counts evaluations, passes, triggers, blocks, supporting and decisive events. The relevance score combines decision influence, profit, risk and stability. Ratings such as highly relevant, negatively acting or insufficiently observed describe the selected historical window only.

Weekly/monthly aggregate tables reveal regime dependence. Signal events provide row-level traceability. Monte Carlo generates possible one-year paths from historical returns and is a robustness test, not a price forecast. Strategy comparison contrasts active rules with Buy-and-Hold and Oracle.

## 9. Architecture

`app.py` starts Streamlit; `_legacy_app.py` orchestrates UI, authentication and workflow. `data_provider.py` normalizes Yahoo Finance and Binance OHLCV. `indicators.py` calculates indicators. `strategy.py` and `telemetry.py` generate and explain signals. `backtest.py` simulates execution. `hyperopt2.py` searches combinations. `monte_carlo.py` tests modeled paths. `storage.py` stores watchlists, history and alerts in SQLite. Plotly renders charts; Streamlit Community Cloud deploys GitHub `main`.

**Flow:** market data → normalization → indicators → criteria → signals → backtest → metrics → Hyperopt/Simulation → robustness → tables and charts.

## 10. Limitations

Historical optimization may overfit. Results depend on symbol, period, interval, fees and data quality. More risk can increase both return and drawdown. Few trades are weak evidence. Importance and sensitivity are diagnostics, not proof. Walk-forward and out-of-sample tests are required before practical use.
""",
    "ru": r"""
# TraidSim – руководство пользователя и описание системы

TraidSim объединяет исторические данные, технические индикаторы, правила, управление риском, бэктест, Hyperopt и проверку устойчивости. Это инструмент технического моделирования, а не инвестиционная рекомендация.

## 1. Рекомендуемый процесс

1. В боковой панели задать список, период, интервал, капитал, комиссии и риск.
2. В **Обзоре** проверить данные, сигнал, оценку, график и бэктест.
3. В **Hyperopt** выбрать цель и допустимые критерии, затем запустить оптимизацию.
4. Оценивать доходность вместе с просадкой, сделками, сходимостью и стабильностью.
5. Нажать **Полностью перенести рекомендацию в симуляцию**.
6. Проверить ту же конфигурацию и период в **Симуляции**.

## 2. Поля боковой панели

- **Сохранённый список / ручной ввод:** загружает сохранённые или введённые через запятую символы.
- **Сохранить список:** записывает текущие символы в SQLite.
- **Период и интервал:** задают глубину истории и размер свечи; периоды индикаторов считаются в свечах.
- **Начальный капитал:** стартовая сумма для сравнений.
- **Риск на сделку:** внутреннее `0,02` означает 2%.
- **Комиссия:** применяется при каждой покупке и продаже.
- **ATR stop-loss / take-profit:** расстояния выхода на основе волатильности.
- **Запуски Hyperopt:** число проверяемых комбинаций.
- **Минимум сделок:** штрафует результаты со слишком малым числом закрытых сделок.
- **Пересчитать:** повторяет расчёт с текущими значениями.

## 3. Обзор

График стратегии совмещает цену и индикаторы. Последний сигнал и оценка суммируют выполненные проверки, но не являются прогнозом. Таблица критериев объясняет сигнал. Рейтинг сравнивает стратегию, Buy-and-Hold, просадку и долю прибыльных сделок. Метрики и сделки можно скачать в CSV.

## 4. Цели и управление Hyperopt

- **Максимальная доходность:** максимизирует исторический результат и может выбирать больший риск.
- **Минимальная просадка:** предпочитает меньшие снижения капитала.
- **Максимальная доля прибыльных сделок:** предпочитает высокий win rate.
- **С учётом риска:** сопоставляет доходность и просадку.
- **Сбалансированная:** объединяет доходность, просадку и win rate.

Флажки задают критерии, которые Hyperopt может сравнивать. Управление риском разрешает оптимизацию риска, стопа и цели. Кнопка запуска для каждой комбинации заново рассчитывает индикаторы, сигналы и бэктест той же системой, что используется в Симуляции.

## 5. Десять критериев

1. **Тренд:** цена и трендовая SMA выше SMA 200; период SMA.
2. **RSI:** RSI внутри диапазона входа; отдельный порог выхода.
3. **MACD:** MACD выше сигнальной линии; быстрая, медленная и сигнальная EMA.
4. **Bollinger:** закрытие выше средней линии; период и отклонение.
5. **Fibonacci:** цена удерживает уровень поддержки 61,8%; период ретроспективы.
6. **Объём:** текущий объём выше среднего, умноженного на минимальный коэффициент.
7. **Стохастик:** %K между границами и выше %D; периоды и пороги.
8. **ATR:** процент ATR внутри допустимого диапазона; период, минимум и максимум.
9. **Ichimoku:** цена выше облака, Tenkan выше Kijun; три периода.
10. **Управление риском:** не ценовой фильтр; задаёт риск позиции, стоп и цель.

## 6. Результаты Hyperopt

- **Доходность, просадка, сделки, стабильность:** главные метрики лучшего запуска.
- **Сходимость:** расстояние до окончательного результата, новые максимумы, лучший Objective, действительные и оштрафованные запуски.
- **Рекомендуемые критерии:** состав лучшей комбинации Да/Нет.
- **Рекомендуемые значения:** параметры выбранных критериев и риска.
- **Перенести в симуляцию:** переносит критерии, значения, риск, ATR-стоп и ATR-цель. Для точного сравнения должны совпадать период, интервал, капитал и комиссия.
- **Важность:** связь параметров с изменением Objective, но не причинность.
- **Тепловая карта:** средний Objective для комбинаций двух ведущих параметров.
- **Чувствительность:** средний Objective по значениям; резкие изменения означают хрупкость, широкое плато — большую устойчивость.
- **Оценка стабильности:** учитывает разброс, положительные результаты и просадку лучших запусков.
- **Buy-and-Hold / Oracle:** пассивный эталон и теоретическая верхняя граница. Oracle не влияет на сигналы.
- **CSV:** все запуски, параметры и метрики.

## 7. Симуляция

Окно дат ограничивает анализ, при этом индикаторы сохраняют необходимую предысторию. Десять переключателей соответствуют Hyperopt. Все активные технические критерии должны выполняться одновременно; управление риском влияет на размер позиции и выходы. Блок параметров показывает только относящиеся к выбранным критериям значения и немедленно пересчитывает сигналы, сделки и результаты.

Основные метрики показывают число активных критериев, проверок, сделок и доходность. Подробная таблица содержит конечный капитал, просадку и win rate.

## 8. Телеметрия и рейтинги

Телеметрия считает проверки, выполнения, триггеры, блокировки, поддерживающие и решающие события. Релевантность объединяет влияние на решения, прибыль, риск и стабильность. Оценки относятся только к выбранному историческому периоду.

Недельные и месячные сводные таблицы показывают зависимость от рыночного режима. События обеспечивают построчную проверяемость. Monte Carlo создаёт возможные годовые траектории из исторических доходностей и служит тестом устойчивости, а не прогнозом. Сравнение сопоставляет стратегию, Buy-and-Hold и Oracle.

## 9. Архитектура

`app.py` запускает Streamlit; `_legacy_app.py` управляет интерфейсом, входом и процессом. `data_provider.py` нормализует Yahoo Finance и Binance OHLCV. `indicators.py` рассчитывает индикаторы. `strategy.py` и `telemetry.py` создают и объясняют сигналы. `backtest.py` моделирует исполнение. `hyperopt2.py` перебирает комбинации. `monte_carlo.py` тестирует смоделированные пути. `storage.py` хранит списки, историю и оповещения в SQLite. Plotly строит графики, Streamlit Community Cloud публикует GitHub `main`.

**Поток:** данные → нормализация → индикаторы → критерии → сигналы → бэктест → метрики → Hyperopt/Симуляция → устойчивость → таблицы и графики.

## 10. Ограничения

Историческая оптимизация может переобучаться. Результаты зависят от инструмента, периода, интервала, комиссий и качества данных. Больший риск повышает как доходность, так и просадку. Малое число сделок является слабым доказательством. Нужны walk-forward и out-of-sample проверки.
""",
}
