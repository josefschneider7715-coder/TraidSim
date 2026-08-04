from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.comparison import (
    comparison_metrics,
    run_buy_and_hold_benchmark,
    run_oracle_benchmark,
    run_strategy_benchmark,
)
from src.comparison_charts import make_oracle_trade_chart
from src.scored_signals import apply_scored_entry_signals


def _eur(value: float) -> str:
    return f"{value:,.0f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(value: float) -> str:
    return f"{value:.2f} %".replace(".", ",")


def _curve(result, column_name: str) -> pd.DataFrame:
    frame = result.equity[["Date", "Equity"]].copy()
    frame["Date"] = pd.to_datetime(frame["Date"])
    return frame.rename(columns={"Equity": column_name})


def _align_four_curves(risk_result, full_result, buy_hold_result, oracle_result) -> pd.DataFrame:
    aligned = _curve(risk_result, "Strategie Risikomodell")
    aligned = aligned.merge(_curve(full_result, "Strategie 100 % Kapital"), on="Date", how="outer")
    aligned = aligned.merge(_curve(buy_hold_result, "Buy and Hold"), on="Date", how="outer")
    aligned = aligned.merge(_curve(oracle_result, "Oracle"), on="Date", how="outer")
    aligned = aligned.sort_values("Date").reset_index(drop=True)
    value_columns = [
        "Strategie Risikomodell",
        "Strategie 100 % Kapital",
        "Buy and Hold",
        "Oracle",
    ]
    aligned[value_columns] = aligned[value_columns].ffill().bfill()
    aligned["Vorteil Risikomodell"] = aligned["Strategie Risikomodell"] - aligned["Buy and Hold"]
    aligned["Vorteil Signalvergleich"] = aligned["Strategie 100 % Kapital"] - aligned["Buy and Hold"]
    return aligned


def _make_dual_strategy_chart(aligned: pd.DataFrame, symbol: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=aligned["Date"], y=aligned["Strategie Risikomodell"], mode="lines", name="Strategie – Risikomodell"))
    fig.add_trace(go.Scatter(x=aligned["Date"], y=aligned["Strategie 100 % Kapital"], mode="lines", name="Strategie – 100 % Kapital"))
    fig.add_trace(go.Scatter(x=aligned["Date"], y=aligned["Buy and Hold"], mode="lines", name="Buy and Hold"))
    fig.update_layout(
        title=f"{symbol} – Risikomodell und reiner Signalvergleich",
        height=560,
        yaxis_title="Kapital",
        legend={"orientation": "h"},
        hovermode="x unified",
    )
    return fig


def _make_advantage_chart(aligned: pd.DataFrame, symbol: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=aligned["Date"], y=aligned["Vorteil Risikomodell"], mode="lines", name="Risikomodell minus Buy and Hold"))
    fig.add_trace(go.Scatter(x=aligned["Date"], y=aligned["Vorteil Signalvergleich"], mode="lines", name="100-%-Signalvergleich minus Buy and Hold"))
    fig.add_hline(y=0, line_dash="dash")
    fig.update_layout(
        title=f"{symbol} – Laufender Vorsprung oder Rückstand",
        height=420,
        yaxis_title="Differenz zum Buy and Hold",
        legend={"orientation": "h"},
        hovermode="x unified",
    )
    return fig


def _make_oracle_chart(aligned: pd.DataFrame, symbol: str) -> go.Figure:
    fig = go.Figure()
    for column, label in [
        ("Strategie Risikomodell", "Strategie – Risikomodell"),
        ("Strategie 100 % Kapital", "Strategie – 100 % Kapital"),
        ("Buy and Hold", "Buy and Hold"),
        ("Oracle", "Theoretisches Optimum (Oracle)"),
    ]:
        fig.add_trace(go.Scatter(x=aligned["Date"], y=aligned[column], mode="lines", name=label))
    fig.update_layout(
        title=f"{symbol} – Vergleich mit theoretischem Optimum",
        height=560,
        yaxis_title="Kapital",
        legend={"orientation": "h"},
        hovermode="x unified",
    )
    return fig


def render_strategy_comparison(
    simulation_df,
    simulation_source_df,
    initial_capital: float,
    risk_per_trade: float,
    atr_stop: float,
    atr_tp: float,
    fee: float,
    selected_symbol: str,
) -> None:
    if simulation_source_df is None or len(simulation_source_df) < 2:
        st.info("Das gewählte Zeitfenster enthält zu wenig Kursdaten für den Strategievergleich.")
        return

    try:
        risk_result = run_strategy_benchmark(
            simulation_df,
            initial_capital=float(initial_capital),
            risk_per_trade=float(risk_per_trade),
            atr_stop_factor=float(atr_stop),
            atr_take_profit_factor=float(atr_tp),
            trading_fee=float(fee),
            position_mode="risk",
        )
        full_result = run_strategy_benchmark(
            simulation_df,
            initial_capital=float(initial_capital),
            risk_per_trade=float(risk_per_trade),
            atr_stop_factor=float(atr_stop),
            atr_take_profit_factor=float(atr_tp),
            trading_fee=float(fee),
            position_mode="full_capital",
        )
        buy_hold_result = run_buy_and_hold_benchmark(
            simulation_source_df,
            initial_capital=float(initial_capital),
            trading_fee=float(fee),
        )
        oracle_result = run_oracle_benchmark(
            simulation_source_df,
            initial_capital=float(initial_capital),
            trading_fee=float(fee),
        )
        aligned = _align_four_curves(risk_result, full_result, buy_hold_result, oracle_result)
        signal_comparison = comparison_metrics(full_result, buy_hold_result, oracle_result, float(initial_capital))
    except Exception as exc:
        st.error(f"Strategievergleich konnte nicht berechnet werden: {exc}")
        return

    st.divider()
    st.write("### Strategievergleich")
    st.caption(
        "Neue Einstiegsmethode: Der SMA-Trend ist Pflicht, sofern aktiviert. Zusätzlich müssen "
        "mindestens drei der weiteren aktiven Bestätigungskriterien erfüllt sein. Der Vergleich "
        "zeigt getrennt das reale Risikomodell und dieselben Signale mit 100 % Kapitaleinsatz."
    )
    st.warning(
        "Das Oracle kennt alle späteren Schlusskurse und ist nicht real handelbar. "
        "Es dient ausschließlich als theoretische Obergrenze."
    )

    risk_end = float(risk_result.metrics.get("Endkapital", initial_capital))
    full_end = float(full_result.metrics.get("Endkapital", initial_capital))
    buy_hold_end = float(buy_hold_result.metrics.get("Endkapital", initial_capital))
    oracle_end = float(oracle_result.metrics.get("Endkapital", initial_capital))

    metric_cols = st.columns(6)
    metric_cols[0].metric("Strategie – Risikomodell", _eur(risk_end), _pct(float(risk_result.metrics.get("Gesamtrendite %", 0.0))))
    metric_cols[1].metric("Strategie – 100 % Kapital", _eur(full_end), _pct(float(full_result.metrics.get("Gesamtrendite %", 0.0))))
    metric_cols[2].metric("Buy-and-Hold-Endkapital", _eur(buy_hold_end), _pct(float(buy_hold_result.metrics.get("Gesamtrendite %", 0.0))))
    metric_cols[3].metric("Signalvorteil", _eur(float(signal_comparison["Vorteil Strategie EUR"])), _pct(float(signal_comparison["Vorteil Strategie %"])))
    metric_cols[4].metric("Oracle-Endkapital", _eur(oracle_end), _pct(float(oracle_result.metrics.get("Gesamtrendite %", 0.0))))
    metric_cols[5].metric(
        "Risikomodell",
        _pct(float(risk_result.metrics.get("Max. Drawdown %", 0.0))),
        f"{int(risk_result.metrics.get('Abgeschlossene Trades', 0))} Trades · {_pct(float(risk_result.metrics.get('Marktzeit %', 0.0)))} Marktzeit",
    )

    st.plotly_chart(_make_dual_strategy_chart(aligned, selected_symbol), use_container_width=True)
    st.plotly_chart(_make_advantage_chart(aligned, selected_symbol), use_container_width=True)
    st.plotly_chart(_make_oracle_chart(aligned, selected_symbol), use_container_width=True)
    st.plotly_chart(make_oracle_trade_chart(simulation_source_df, oracle_result.trades, selected_symbol), use_container_width=True)

    risk_tab, signal_tab, buy_hold_tab, oracle_tab = st.tabs(
        ["Risikomodell-Trades", "100-%-Signal-Trades", "Buy-and-Hold", "Oracle-Trades"]
    )
    with risk_tab:
        st.dataframe(risk_result.metrics, use_container_width=True)
        if risk_result.trades.empty:
            st.info("Keine Trades im Risikomodell.")
        else:
            st.dataframe(risk_result.trades, use_container_width=True)
    with signal_tab:
        st.dataframe(full_result.metrics, use_container_width=True)
        if full_result.trades.empty:
            st.info("Keine Trades im 100-%-Signalvergleich.")
        else:
            st.dataframe(full_result.trades, use_container_width=True)
    with buy_hold_tab:
        st.dataframe(buy_hold_result.metrics, use_container_width=True)
        st.caption(
            "Buy and Hold kauft zum ersten Eröffnungskurs des gewählten Zeitfensters und verkauft "
            "zum letzten Schlusskurs. Kauf- und Verkaufsgebühr werden berücksichtigt."
        )
        if buy_hold_result.trades.empty:
            st.info("Keine Buy-and-Hold-Transaktionen vorhanden.")
        else:
            st.dataframe(buy_hold_result.trades, use_container_width=True)
    with oracle_tab:
        if oracle_result.trades.empty:
            st.info("Das Oracle bleibt in diesem Zeitfenster vollständig in Cash.")
        else:
            st.dataframe(oracle_result.trades, use_container_width=True)


_legacy_path = Path(__file__).with_name("_legacy_app.py")
_source = _legacy_path.read_text(encoding="utf-8-sig")

_signal_marker = "simulation_df = apply_enabled_criteria_signals(simulation_source_df, enabled_criteria)"
_signal_replacement = "simulation_df = apply_enabled_criteria_signals(simulation_source_df, enabled_criteria, params=simulation_strategy_params)"
if _signal_marker not in _source:
    raise RuntimeError("Einfügepunkt für die neue Einstiegsmethode wurde nicht gefunden.")
_source = _source.replace(_signal_marker, _signal_replacement, 1)

_comparison_marker = '''        st.download_button(
            tr("criteria_download"),'''
_comparison_injected = '''        render_strategy_comparison(
            simulation_df=simulation_df,
            simulation_source_df=simulation_source_df,
            initial_capital=initial_capital,
            risk_per_trade=simulation_risk_per_trade,
            atr_stop=simulation_atr_stop,
            atr_tp=simulation_atr_tp,
            fee=fee,
            selected_symbol=selected_symbol,
        )

        st.download_button(
            tr("criteria_download"),'''
if _comparison_marker not in _source:
    raise RuntimeError("Einfügepunkt für den Strategievergleich wurde nicht gefunden.")
_source = _source.replace(_comparison_marker, _comparison_injected, 1)

exec(compile(_source, str(_legacy_path), "exec"), globals(), globals())
