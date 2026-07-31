from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.hyperopt_enhanced import (
    OBJECTIVE_LABELS,
    best_hyperopt_parameters,
    parameter_importance,
    profit_parameter_importance,
    run_hyperopt,
)


CRITERIA_LABELS = {
    "trend": "SMA-Trend",
    "rsi": "RSI",
    "macd": "MACD",
    "bollinger": "Bollinger-Bänder",
    "fibonacci": "Fibonacci",
    "volume": "Volumen",
    "stoch": "Stochastik",
    "atr": "ATR-Volatilität",
    "ichimoku": "Ichimoku",
    "risk_management": "Risikomanagement optimieren",
}

PARAMETER_LABELS = {
    "sma_trend_period": "SMA-Trendperiode",
    "rsi_period": "RSI-Periode",
    "rsi_min": "RSI-Untergrenze",
    "rsi_max": "RSI-Obergrenze",
    "exit_rsi_max": "RSI-Exit",
    "macd_fast": "MACD schnell",
    "macd_slow": "MACD langsam",
    "macd_signal": "MACD Signal",
    "bb_period": "Bollinger-Periode",
    "bb_std": "Bollinger-Abweichung",
    "fib_lookback": "Fibonacci-Rückblick",
    "volume_period": "Volumenperiode",
    "volume_factor": "Volumenfaktor",
    "stoch_period": "Stochastik-Periode",
    "stoch_signal": "Stochastik-Signal",
    "stoch_min": "Stochastik-Untergrenze",
    "stoch_max": "Stochastik-Obergrenze",
    "atr_period": "ATR-Periode",
    "atr_min_pct": "ATR-Untergrenze",
    "atr_max_pct": "ATR-Obergrenze",
    "ichimoku_tenkan": "Ichimoku Tenkan",
    "ichimoku_kijun": "Ichimoku Kijun",
    "ichimoku_senkou_b": "Ichimoku Senkou B",
    "risk_per_trade": "Risiko je Trade",
    "atr_stop_factor": "ATR-Stop-Faktor",
    "atr_take_profit_factor": "ATR-Take-Profit-Faktor",
}


def _importance_chart(frame: pd.DataFrame, title: str) -> go.Figure:
    display = frame.head(15).sort_values("Einfluss %", ascending=True).copy()
    display["Parametername"] = display["Parameter"].map(PARAMETER_LABELS).fillna(display["Parameter"])
    fig = go.Figure(
        go.Bar(
            x=display["Einfluss %"],
            y=display["Parametername"],
            orientation="h",
            customdata=display[["Bester Wert", "Ergebnisspanne"]],
            hovertemplate=(
                "%{y}<br>Einfluss: %{x:.1f}%"
                "<br>Bester getesteter Wert: %{customdata[0]}"
                "<br>Ergebnisspanne: %{customdata[1]:.2f}<extra></extra>"
            ),
        )
    )
    fig.update_layout(title=title, height=max(420, len(display) * 30), xaxis_title="Relativer Einfluss", yaxis_title="")
    return fig


def _sensitivity_chart(results: pd.DataFrame, parameter: str, target: str) -> go.Figure:
    grouped = (
        results[results["Objective"] > -999_000]
        .groupby(parameter, as_index=False)[target]
        .agg(["mean", "min", "max"])
        .reset_index()
    )
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=grouped[parameter],
            y=grouped["mean"],
            mode="lines+markers",
            name="Mittelwert",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=grouped[parameter],
            y=grouped["max"],
            mode="lines",
            name="Bestes Ergebnis",
            line={"dash": "dot"},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=grouped[parameter],
            y=grouped["min"],
            mode="lines",
            name="Schlechtestes Ergebnis",
            line={"dash": "dot"},
        )
    )
    fig.update_layout(
        title=f"Sensitivität: {PARAMETER_LABELS.get(parameter, parameter)}",
        xaxis_title=PARAMETER_LABELS.get(parameter, parameter),
        yaxis_title=target,
        height=430,
        legend={"orientation": "h"},
    )
    return fig


def _best_parameter_table(best_params, enabled_criteria: dict[str, bool]) -> pd.DataFrame:
    values = vars(best_params)
    rows = []
    for key, value in values.items():
        if key.startswith("risk_") or key.startswith("atr_stop") or key.startswith("atr_take"):
            if not enabled_criteria.get("risk_management", False):
                continue
        rows.append({"Parameter": PARAMETER_LABELS.get(key, key), "Wert": value})
    return pd.DataFrame(rows)


def render_hyperopt2(
    df: pd.DataFrame,
    selected_symbol: str,
    initial_capital: float,
    trading_fee: float,
    risk_per_trade: float,
    atr_stop_factor: float,
    atr_take_profit_factor: float,
) -> None:
    st.subheader(f"Hyperopt 2 (Beta): {selected_symbol}")
    st.info(
        "Hyperopt 2 arbeitet vollständig getrennt vom bestehenden Hyperopt. "
        "Es verwendet Trend plus eine optimierbare Mindestzahl an Bestätigungen und kann gezielt "
        "auf Gewinn, Gewinn minus Drawdown oder eine ausgewogene Bewertung optimieren."
    )

    objective_label_to_key = {label: key for key, label in OBJECTIVE_LABELS.items()}
    config_col1, config_col2, config_col3 = st.columns(3)
    selected_objective_label = config_col1.selectbox(
        "Optimierungsziel",
        list(objective_label_to_key),
        index=0,
        key=f"hyperopt2_objective_{selected_symbol}",
    )
    minimum_confirmations = config_col2.slider(
        "Mindest-Bestätigungen",
        min_value=1,
        max_value=6,
        value=3,
        step=1,
        key=f"hyperopt2_confirmations_{selected_symbol}",
    )
    max_trials = config_col3.slider(
        "Durchläufe",
        min_value=50,
        max_value=2000,
        value=500,
        step=50,
        key=f"hyperopt2_trials_{selected_symbol}",
    )

    st.write("### Kriterien und Parametergruppen")
    defaults = {
        "trend": True,
        "rsi": True,
        "macd": True,
        "bollinger": True,
        "fibonacci": False,
        "volume": True,
        "stoch": False,
        "atr": False,
        "ichimoku": False,
        "risk_management": True,
    }
    enabled_criteria: dict[str, bool] = {}
    criterion_columns = st.columns(3)
    for index, (key, label) in enumerate(CRITERIA_LABELS.items()):
        with criterion_columns[index % 3]:
            enabled_criteria[key] = st.checkbox(
                label,
                value=defaults[key],
                key=f"hyperopt2_criterion_{selected_symbol}_{key}",
            )

    available_dates = pd.to_datetime(df["Date"]).dt.date
    min_date = available_dates.min()
    max_date = available_dates.max()
    date_col1, date_col2, trade_col = st.columns(3)
    start_date = date_col1.date_input(
        "Startdatum",
        value=min_date,
        min_value=min_date,
        max_value=max_date,
        key=f"hyperopt2_start_{selected_symbol}",
    )
    end_date = date_col2.date_input(
        "Enddatum",
        value=max_date,
        min_value=min_date,
        max_value=max_date,
        key=f"hyperopt2_end_{selected_symbol}",
    )
    min_trades = trade_col.number_input(
        "Mindestzahl abgeschlossener Trades",
        min_value=0,
        max_value=50,
        value=3,
        step=1,
        key=f"hyperopt2_min_trades_{selected_symbol}",
    )

    if start_date > end_date:
        st.error("Das Startdatum muss vor dem Enddatum liegen.")
        return

    source_df = df[
        (pd.to_datetime(df["Date"]).dt.date >= start_date)
        & (pd.to_datetime(df["Date"]).dt.date <= end_date)
    ].copy()
    st.caption(f"Testzeitraum: {start_date} bis {end_date} mit {len(source_df)} Kurszeilen.")

    run_button = st.button("Hyperopt 2 starten", type="primary", key=f"run_hyperopt2_{selected_symbol}")
    if run_button:
        if len(source_df) < 220:
            st.warning("Für belastbare Ergebnisse sollte das Zeitfenster mindestens etwa 220 Kurszeilen enthalten.")
        with st.spinner(f"Hyperopt 2 testet {max_trials} Parameterkombinationen für {selected_symbol} …"):
            result = run_hyperopt(
                source_df,
                initial_capital=float(initial_capital),
                trading_fee=float(trading_fee),
                risk_per_trade=float(risk_per_trade),
                atr_stop_factor=float(atr_stop_factor),
                atr_take_profit_factor=float(atr_take_profit_factor),
                max_trials=int(max_trials),
                min_trades=int(min_trades),
                enabled_criteria=enabled_criteria,
                objective_mode=objective_label_to_key[selected_objective_label],
                minimum_confirmations=int(minimum_confirmations),
            )
            st.session_state["hyperopt2_result"] = {
                "symbol": selected_symbol,
                "start": start_date,
                "end": end_date,
                "objective": selected_objective_label,
                "confirmations": minimum_confirmations,
                "criteria": enabled_criteria,
                "data": result,
            }

    stored = st.session_state.get("hyperopt2_result")
    if not stored or stored.get("symbol") != selected_symbol:
        st.info("Starte Hyperopt 2, um die neue Optimierung zu berechnen.")
        return

    results = stored["data"]
    if results.empty:
        st.warning("Hyperopt 2 hat keine Ergebnisse erzeugt.")
        return

    valid = results[results["Objective"] > -999_000]
    if valid.empty:
        st.warning("Keine Kombination erfüllt die Mindestzahl an Trades. Mindest-Trades senken oder Kriterien lockern.")
        return

    best = valid.iloc[0]
    metric_cols = st.columns(6)
    metric_cols[0].metric("Optimierungsziel", stored["objective"])
    metric_cols[1].metric("Beste Rendite", f"{float(best['Gesamtrendite %']):.2f} %")
    metric_cols[2].metric("Endkapital", f"{float(best['Endkapital']):,.0f} €")
    metric_cols[3].metric("Max. Drawdown", f"{float(best['Max. Drawdown %']):.2f} %")
    metric_cols[4].metric("Trades", int(best["Abgeschlossene Trades"]))
    metric_cols[5].metric("Gebühren", f"{float(best['Gebuehren gesamt']):,.0f} €")

    best_params = best_hyperopt_parameters(valid)
    if best_params is not None:
        st.write("### Beste gefundene Parameter")
        st.dataframe(_best_parameter_table(best_params, stored["criteria"]), use_container_width=True, hide_index=True)

    profit_importance = profit_parameter_importance(valid)
    drawdown_importance = parameter_importance(valid, "Max. Drawdown %")
    hitrate_importance = parameter_importance(valid, "Trefferquote %")
    fee_importance = parameter_importance(valid, "Gebuehren gesamt")

    st.write("### Welche Parameter bestimmen den maximalen Gewinn?")
    st.caption(
        "Der Einfluss wird aus der Spannweite der durchschnittlichen Rendite zwischen den getesteten Parameterwerten berechnet. "
        "100 % kennzeichnet den stärksten Gewinnhebel dieses Laufs, nicht eine garantierte Renditesteigerung."
    )
    st.plotly_chart(_importance_chart(profit_importance, "Parameter-Einfluss auf den Gewinn"), use_container_width=True)

    analysis_tab1, analysis_tab2, analysis_tab3, analysis_tab4 = st.tabs(
        ["Gewinn", "Drawdown", "Trefferquote", "Gebühren"]
    )
    for tab, frame in [
        (analysis_tab1, profit_importance),
        (analysis_tab2, drawdown_importance),
        (analysis_tab3, hitrate_importance),
        (analysis_tab4, fee_importance),
    ]:
        with tab:
            display = frame.copy()
            if not display.empty:
                display["Parameter"] = display["Parameter"].map(PARAMETER_LABELS).fillna(display["Parameter"])
            st.dataframe(display, use_container_width=True, hide_index=True)

    if not profit_importance.empty:
        st.write("### Sensitivitätsanalyse")
        parameter_options = profit_importance["Parameter"].tolist()
        selected_parameter = st.selectbox(
            "Parameter auswählen",
            parameter_options,
            format_func=lambda value: PARAMETER_LABELS.get(value, value),
            key=f"hyperopt2_sensitivity_parameter_{selected_symbol}",
        )
        target_label_to_column = {
            "Rendite": "Gesamtrendite %",
            "Drawdown": "Max. Drawdown %",
            "Trefferquote": "Trefferquote %",
            "Gebühren": "Gebuehren gesamt",
        }
        selected_target_label = st.selectbox(
            "Zielkennzahl",
            list(target_label_to_column),
            key=f"hyperopt2_sensitivity_target_{selected_symbol}",
        )
        st.plotly_chart(
            _sensitivity_chart(valid, selected_parameter, target_label_to_column[selected_target_label]),
            use_container_width=True,
        )

    st.write("### Alle getesteten Kombinationen")
    st.dataframe(results, use_container_width=True)
    st.download_button(
        "Hyperopt-2-Ergebnisse als CSV herunterladen",
        results.to_csv(index=False).encode("utf-8"),
        f"{selected_symbol}_hyperopt2.csv",
        "text/csv",
        key=f"download_hyperopt2_{selected_symbol}",
    )
