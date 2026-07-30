from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.comparison import (
    align_equity_curves,
    comparison_metrics,
    run_buy_and_hold_benchmark,
    run_oracle_benchmark,
    run_strategy_benchmark,
)
from src.comparison_charts import (
    make_oracle_comparison_chart,
    make_oracle_trade_chart,
    make_strategy_vs_buy_hold_chart,
)


def _eur(value: float) -> str:
    return f"{value:,.0f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(value: float) -> str:
    return f"{value:.2f} %".replace(".", ",")


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
    """Zeigt den Vergleich direkt nach der Monte-Carlo-Auswertung an."""

    if simulation_source_df is None or len(simulation_source_df) < 2:
        st.info("Das gewählte Zeitfenster enthält zu wenig Kursdaten für den Strategievergleich.")
        return

    try:
        strategy_result = run_strategy_benchmark(
            simulation_df,
            initial_capital=float(initial_capital),
            risk_per_trade=float(risk_per_trade),
            atr_stop_factor=float(atr_stop),
            atr_take_profit_factor=float(atr_tp),
            trading_fee=float(fee),
            position_mode="risk",
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
        aligned = align_equity_curves(strategy_result, buy_hold_result, oracle_result)
        comparison = comparison_metrics(
            strategy_result,
            buy_hold_result,
            oracle_result,
            float(initial_capital),
        )
    except Exception as exc:
        st.error(f"Strategievergleich konnte nicht berechnet werden: {exc}")
        return

    st.divider()
    st.write("### Strategievergleich")
    st.caption(
        "Verwendet automatisch das gewählte Simulationszeitfenster, die aktiven Kriterien, "
        "das Startkapital, Risiko pro Trade, ATR-Stop, ATR-Take-Profit und die Gebühr pro Order."
    )
    st.warning(
        "Das Oracle kennt alle späteren Schlusskurse und ist nicht real handelbar. "
        "Es dient ausschließlich als theoretische Obergrenze."
    )

    strategy_end = float(strategy_result.metrics.get("Endkapital", initial_capital))
    buy_hold_end = float(buy_hold_result.metrics.get("Endkapital", initial_capital))
    oracle_end = float(oracle_result.metrics.get("Endkapital", initial_capital))
    strategy_return = float(strategy_result.metrics.get("Gesamtrendite %", 0.0))
    buy_hold_return = float(buy_hold_result.metrics.get("Gesamtrendite %", 0.0))
    oracle_return = float(oracle_result.metrics.get("Gesamtrendite %", 0.0))
    strategy_drawdown = float(strategy_result.metrics.get("Max. Drawdown %", 0.0))
    strategy_trades = int(strategy_result.metrics.get("Abgeschlossene Trades", 0))
    market_time = float(strategy_result.metrics.get("Marktzeit %", 0.0))

    metric_cols = st.columns(6)
    metric_cols[0].metric("Strategie-Endkapital", _eur(strategy_end), _pct(strategy_return))
    metric_cols[1].metric("Buy-and-Hold-Endkapital", _eur(buy_hold_end), _pct(buy_hold_return))
    metric_cols[2].metric(
        "Vorteil Strategie",
        _eur(float(comparison["Vorteil Strategie EUR"])),
        _pct(float(comparison["Vorteil Strategie %"])),
    )
    metric_cols[3].metric("Oracle-Endkapital", _eur(oracle_end), _pct(oracle_return))
    metric_cols[4].metric(
        "Erreichtes Potenzial",
        _pct(float(comparison["Erreichtes theoretisches Potenzial %"])),
        f"Abstand {_eur(float(comparison['Abstand zum Oracle EUR']))}",
    )
    metric_cols[5].metric(
        "Strategie-Risiko",
        _pct(strategy_drawdown),
        f"{strategy_trades} Trades · {_pct(market_time)} Marktzeit",
    )

    st.plotly_chart(
        make_strategy_vs_buy_hold_chart(aligned, selected_symbol),
        use_container_width=True,
    )
    st.plotly_chart(
        make_oracle_comparison_chart(aligned, selected_symbol, logarithmic=False),
        use_container_width=True,
    )
    st.plotly_chart(
        make_oracle_trade_chart(simulation_source_df, oracle_result.trades, selected_symbol),
        use_container_width=True,
    )

    details_tab, oracle_tab = st.tabs(["Kennzahlen und Strategie-Trades", "Oracle-Trades"])
    with details_tab:
        st.dataframe(
            [strategy_result.metrics, buy_hold_result.metrics, oracle_result.metrics],
            use_container_width=True,
        )
        if strategy_result.trades.empty:
            st.info("Keine Strategie-Trades im gewählten Zeitfenster.")
        else:
            st.dataframe(strategy_result.trades, use_container_width=True)
    with oracle_tab:
        if oracle_result.trades.empty:
            st.info("Das Oracle bleibt in diesem Zeitfenster vollständig in Cash.")
        else:
            st.dataframe(oracle_result.trades, use_container_width=True)


# Die bestehende Anwendung wird weiterhin im ursprünglichen Streamlit-Kontext
# ausgeführt. Vor dem Kompilieren wird nur ein direkter Funktionsaufruf an der
# gewünschten Stelle nach dem Monte-Carlo-Bereich eingefügt.
_legacy_path = Path(__file__).with_name("_legacy_app.py")
_source = _legacy_path.read_text(encoding="utf-8-sig")
_marker = '''        st.download_button(
            "Kriterien-Auswertung als CSV herunterladen",'''
_injected = '''        render_strategy_comparison(
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

if _marker not in _source:
    raise RuntimeError("Einfügepunkt für den Strategievergleich wurde nicht gefunden.")

_source = _source.replace(_marker, _injected, 1)
exec(compile(_source, str(_legacy_path), "exec"), globals(), globals())
