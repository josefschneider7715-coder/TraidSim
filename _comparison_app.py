from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.comparison import comparison_metrics, run_buy_and_hold_benchmark, run_oracle_benchmark, run_strategy_benchmark
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
    columns = ["Strategie Risikomodell", "Strategie 100 % Kapital", "Buy and Hold", "Oracle"]
    aligned[columns] = aligned[columns].ffill().bfill()
    aligned["Vorteil Risikomodell"] = aligned["Strategie Risikomodell"] - aligned["Buy and Hold"]
    aligned["Vorteil Signalvergleich"] = aligned["Strategie 100 % Kapital"] - aligned["Buy and Hold"]
    return aligned


def _make_dual_strategy_chart(aligned: pd.DataFrame, symbol: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=aligned["Date"], y=aligned["Strategie Risikomodell"], mode="lines", name="Strategie – Risikomodell"))
    fig.add_trace(go.Scatter(x=aligned["Date"], y=aligned["Strategie 100 % Kapital"], mode="lines", name="Strategie – 100 % Kapital"))
    fig.add_trace(go.Scatter(x=aligned["Date"], y=aligned["Buy and Hold"], mode="lines", name="Buy and Hold"))
    fig.update_layout(title=f"{symbol} – Risikomodell und reiner Signalvergleich", height=560, yaxis_title="Kapital", legend={"orientation": "h"}, hovermode="x unified")
    return fig


def _make_advantage_chart(aligned: pd.DataFrame, symbol: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=aligned["Date"], y=aligned["Vorteil Risikomodell"], mode="lines", name="Risikomodell minus Buy and Hold"))
    fig.add_trace(go.Scatter(x=aligned["Date"], y=aligned["Vorteil Signalvergleich"], mode="lines", name="100-%-Signalvergleich minus Buy and Hold"))
    fig.add_hline(y=0, line_dash="dash")
    fig.update_layout(title=f"{symbol} – Laufender Vorsprung oder Rückstand", height=420, yaxis_title="Differenz zum Buy and Hold", legend={"orientation": "h"}, hovermode="x unified")
    return fig


def _make_oracle_chart(aligned: pd.DataFrame, symbol: str) -> go.Figure:
    fig = go.Figure()
    for column, label in [("Strategie Risikomodell", "Strategie – Risikomodell"), ("Strategie 100 % Kapital", "Strategie – 100 % Kapital"), ("Buy and Hold", "Buy and Hold"), ("Oracle", "Theoretisches Optimum (Oracle)")]:
        fig.add_trace(go.Scatter(x=aligned["Date"], y=aligned[column], mode="lines", name=label))
    fig.update_layout(title=f"{symbol} – Vergleich mit theoretischem Optimum", height=560, yaxis_title="Kapital", legend={"orientation": "h"}, hovermode="x unified")
    return fig


def render_strategy_comparison(simulation_df, simulation_source_df, initial_capital: float, risk_per_trade: float, atr_stop: float, atr_tp: float, fee: float, selected_symbol: str) -> None:
    if simulation_source_df is None or len(simulation_source_df) < 2:
        st.info("Das gewählte Zeitfenster enthält zu wenig Kursdaten für den Strategievergleich.")
        return
    try:
        risk_result = run_strategy_benchmark(simulation_df, initial_capital=float(initial_capital), risk_per_trade=float(risk_per_trade), atr_stop_factor=float(atr_stop), atr_take_profit_factor=float(atr_tp), trading_fee=float(fee), position_mode="risk")
        full_result = run_strategy_benchmark(simulation_df, initial_capital=float(initial_capital), risk_per_trade=float(risk_per_trade), atr_stop_factor=float(atr_stop), atr_take_profit_factor=float(atr_tp), trading_fee=float(fee), position_mode="full_capital")
        buy_hold_result = run_buy_and_hold_benchmark(simulation_source_df, initial_capital=float(initial_capital), trading_fee=float(fee))
        oracle_result = run_oracle_benchmark(simulation_source_df, initial_capital=float(initial_capital), trading_fee=float(fee))
        aligned = _align_four_curves(risk_result, full_result, buy_hold_result, oracle_result)
        signal_comparison = comparison_metrics(full_result, buy_hold_result, oracle_result, float(initial_capital))
    except Exception as exc:
        st.error(f"Strategievergleich konnte nicht berechnet werden: {exc}")
        return
    st.divider(); st.write("### Strategievergleich")
    st.caption("Neue Einstiegsmethode: Der SMA-Trend ist Pflicht, sofern aktiviert. Zusätzlich müssen mindestens drei der weiteren aktiven Bestätigungskriterien erfüllt sein.")
    st.warning("Das Oracle kennt alle späteren Schlusskurse und ist nicht real handelbar. Es dient ausschließlich als theoretische Obergrenze.")
    risk_end = float(risk_result.metrics.get("Endkapital", initial_capital)); full_end = float(full_result.metrics.get("Endkapital", initial_capital)); buy_hold_end = float(buy_hold_result.metrics.get("Endkapital", initial_capital)); oracle_end = float(oracle_result.metrics.get("Endkapital", initial_capital))
    cols = st.columns(6)
    cols[0].metric("Strategie – Risikomodell", _eur(risk_end), _pct(float(risk_result.metrics.get("Gesamtrendite %", 0.0))))
    cols[1].metric("Strategie – 100 % Kapital", _eur(full_end), _pct(float(full_result.metrics.get("Gesamtrendite %", 0.0))))
    cols[2].metric("Buy-and-Hold-Endkapital", _eur(buy_hold_end), _pct(float(buy_hold_result.metrics.get("Gesamtrendite %", 0.0))))
    cols[3].metric("Signalvorteil", _eur(float(signal_comparison["Vorteil Strategie EUR"])), _pct(float(signal_comparison["Vorteil Strategie %"])))
    cols[4].metric("Oracle-Endkapital", _eur(oracle_end), _pct(float(oracle_result.metrics.get("Gesamtrendite %", 0.0))))
    cols[5].metric("Risikomodell", _pct(float(risk_result.metrics.get("Max. Drawdown %", 0.0))), f"{int(risk_result.metrics.get('Abgeschlossene Trades', 0))} Trades")
    st.plotly_chart(_make_dual_strategy_chart(aligned, selected_symbol), use_container_width=True)
    st.plotly_chart(_make_advantage_chart(aligned, selected_symbol), use_container_width=True)
    st.plotly_chart(_make_oracle_chart(aligned, selected_symbol), use_container_width=True)
    st.plotly_chart(make_oracle_trade_chart(simulation_source_df, oracle_result.trades, selected_symbol), use_container_width=True)
    risk_tab, signal_tab, buy_hold_tab, oracle_tab = st.tabs(["Risikomodell-Trades", "100-%-Signal-Trades", "Buy-and-Hold", "Oracle-Trades"])
    with risk_tab: st.dataframe(risk_result.metrics, use_container_width=True); st.dataframe(risk_result.trades, use_container_width=True)
    with signal_tab: st.dataframe(full_result.metrics, use_container_width=True); st.dataframe(full_result.trades, use_container_width=True)
    with buy_hold_tab: st.dataframe(buy_hold_result.metrics, use_container_width=True); st.dataframe(buy_hold_result.trades, use_container_width=True)
    with oracle_tab: st.dataframe(oracle_result.trades, use_container_width=True)


_legacy_path = Path(__file__).with_name("_legacy_app.py")
_source = _legacy_path.read_text(encoding="utf-8-sig")
_signal_marker = "simulation_df = apply_enabled_criteria_signals(simulation_source_df, enabled_criteria)"
if _signal_marker not in _source: raise RuntimeError("Einfügepunkt für die neue Einstiegsmethode wurde nicht gefunden.")
_source = _source.replace(_signal_marker, "simulation_df = apply_scored_entry_signals(simulation_source_df, enabled_criteria, minimum_confirmations=3)", 1)
_comparison_marker = '''        st.download_button(
            "Kriterien-Auswertung als CSV herunterladen",'''
_comparison_injected = '''        render_strategy_comparison(
            simulation_df=simulation_df,
            simulation_source_df=simulation_source_df,
            initial_capital=initial_capital,
            risk_per_trade=risk_per_trade,
            atr_stop=atr_stop,
            atr_tp=atr_tp,
            fee=fee,
            selected_symbol=selected_symbol,
        )

        st.download_button(
            "Kriterien-Auswertung als CSV herunterladen",'''
if _comparison_marker not in _source: raise RuntimeError("Einfügepunkt für den Strategievergleich wurde nicht gefunden.")
_source = _source.replace(_comparison_marker, _comparison_injected, 1)
exec(compile(_source, str(_legacy_path), "exec"), globals(), globals())
