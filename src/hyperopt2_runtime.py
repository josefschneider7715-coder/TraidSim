from __future__ import annotations


def inject_hyperopt2(source: str) -> str:
    import_marker = "from src.scored_signals import apply_scored_entry_signals\n"
    import_replacement = (
        "from src.scored_signals import apply_scored_entry_signals\n"
        "from src.hyperopt_enhanced import OBJECTIVE_LABELS, profit_parameter_importance, run_hyperopt as run_hyperopt2\n"
    )
    if import_marker in source and "from src.hyperopt_enhanced import" not in source:
        source = source.replace(import_marker, import_replacement, 1)

    exec_marker = 'exec(compile(_source, str(_legacy_path), "exec"), globals(), globals())'
    injected = '''
_tab_marker = 'overview_tab, hyperopt_tab, telemetry_tab = st.tabs(["Uebersicht", "Hyperopt", "Simulation"])'
_tab_replacement = 'overview_tab, hyperopt_tab, hyperopt2_tab, telemetry_tab = st.tabs(["Uebersicht", "Hyperopt", "Hyperopt 2", "Simulation"])'
if _tab_marker not in _source:
    raise RuntimeError("Einfügepunkt für Hyperopt 2 wurde nicht gefunden.")
_source = _source.replace(_tab_marker, _tab_replacement, 1)

_hyperopt2_block_marker = 'with telemetry_tab:\n'
_hyperopt2_block = '''with hyperopt2_tab:
    st.subheader(f"Hyperopt 2: {selected_symbol}")
    st.caption(
        "Hyperopt 2 verwendet dieselbe Einstiegsmethode wie die Simulation: Trendfilter plus "
        "mindestens drei Bestätigungskriterien."
    )

    objective_mode = st.selectbox(
        "Optimierungsziel",
        options=list(OBJECTIVE_LABELS.keys()),
        format_func=lambda key: OBJECTIVE_LABELS[key],
        key=f"hyperopt2_objective_{selected_symbol}",
    )
    trial_count = st.slider(
        "Anzahl Optimierungsdurchläufe",
        min_value=25,
        max_value=500,
        value=100,
        step=25,
        key=f"hyperopt2_trials_{selected_symbol}",
    )
    minimum_trades_h2 = st.number_input(
        "Mindestanzahl abgeschlossener Trades",
        min_value=0,
        max_value=100,
        value=1,
        step=1,
        key=f"hyperopt2_min_trades_{selected_symbol}",
    )

    if st.button("Hyperopt 2 starten", type="primary", key=f"run_hyperopt2_{selected_symbol}"):
        with st.spinner("Hyperopt 2 analysiert Parameterkombinationen ..."):
            try:
                h2_results = run_hyperopt2(
                    df,
                    initial_capital=initial_capital,
                    trading_fee=fee,
                    risk_per_trade=risk_per_trade,
                    atr_stop_factor=atr_stop,
                    atr_take_profit_factor=atr_tp,
                    max_trials=int(trial_count),
                    min_trades=int(minimum_trades_h2),
                    objective_mode=objective_mode,
                    minimum_confirmations=3,
                )
                st.session_state[f"hyperopt2_results_{selected_symbol}"] = h2_results
            except Exception as exc:
                st.error(f"Hyperopt 2 konnte nicht ausgeführt werden: {exc}")

    h2_results = st.session_state.get(f"hyperopt2_results_{selected_symbol}")
    if h2_results is not None and not h2_results.empty:
        best = h2_results.iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Beste Rendite", f"{float(best.get('Gesamtrendite %', 0.0)):.2f} %")
        c2.metric("Endkapital", f"{float(best.get('Endkapital', initial_capital)):,.0f} €")
        c3.metric("Max. Drawdown", f"{float(best.get('Max. Drawdown %', 0.0)):.2f} %")
        c4.metric("Trades", int(best.get('Abgeschlossene Trades', 0)))

        st.write("### Beste getestete Kombinationen")
        result_columns = [
            column for column in [
                "Durchlauf", "Optimierungsziel", "Objective", "Gesamtrendite %",
                "Endkapital", "Max. Drawdown %", "Abgeschlossene Trades",
                "Trefferquote %", "Gebuehren gesamt"
            ] if column in h2_results.columns
        ]
        st.dataframe(h2_results[result_columns].head(25), use_container_width=True)

        st.write("### Wichtigste Parameter für maximalen Gewinn")
        importance = profit_parameter_importance(h2_results)
        if importance.empty:
            st.info("Für die Einflussanalyse wurden noch nicht genügend unterschiedliche gültige Ergebnisse erzeugt.")
        else:
            st.dataframe(importance.head(20), use_container_width=True)
            st.bar_chart(importance.head(12).set_index("Parameter")["Einfluss %"])

        st.write("### Vollständige Parameter der besten Kombination")
        excluded = {
            "Durchlauf", "Optimierungsziel", "Objective", "Gesamtrendite %",
            "Max. Drawdown %", "Abgeschlossene Trades", "Trefferquote %",
            "Gebuehren gesamt", "Gebuehren %", "Endkapital"
        }
        parameter_rows = [
            {"Parameter": column, "Wert": best[column]}
            for column in h2_results.columns if column not in excluded
        ]
        st.dataframe(pd.DataFrame(parameter_rows), use_container_width=True)

with telemetry_tab:
'''
if _hyperopt2_block_marker not in _source:
    raise RuntimeError("Inhaltspunkt für Hyperopt 2 wurde nicht gefunden.")
_source = _source.replace(_hyperopt2_block_marker, _hyperopt2_block, 1)

exec(compile(_source, str(_legacy_path), "exec"), globals(), globals())
'''.strip()
    if exec_marker not in source:
        raise RuntimeError("Ausführungspunkt für Hyperopt 2 wurde nicht gefunden.")
    return source.replace(exec_marker, injected, 1)
