from __future__ import annotations

import hashlib
import hmac
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.comparison import (  # noqa: E402
    align_equity_curves,
    comparison_metrics,
    run_buy_and_hold_benchmark,
    run_oracle_benchmark,
    run_strategy_benchmark,
)
from src.comparison_charts import (  # noqa: E402
    make_oracle_comparison_chart,
    make_oracle_trade_chart,
    make_strategy_vs_buy_hold_chart,
)
from src.data_provider import download_data  # noqa: E402
from src.indicators import add_indicators  # noqa: E402
from src.strategy import generate_signals  # noqa: E402
from src.telemetry import CRITERIA, apply_enabled_criteria_signals  # noqa: E402


st.set_page_config(page_title="TraidSim – Strategievergleich", page_icon="📈", layout="wide")


def _get_auth_config() -> dict:
    try:
        return dict(st.secrets.get("auth", {}))
    except Exception:
        return {}


def _password_matches(password: str, password_hash: str) -> bool:
    entered_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(entered_hash, password_hash)


def _require_login() -> str:
    auth_config = _get_auth_config()
    users = dict(auth_config.get("users", {}))
    if not users and auth_config.get("username") and auth_config.get("password_sha256"):
        users = {str(auth_config["username"]): str(auth_config["password_sha256"])}

    if not users:
        st.error("Login ist nicht eingerichtet. Bitte .streamlit/secrets.toml konfigurieren.")
        st.stop()

    if st.session_state.get("authenticated"):
        username = str(st.session_state.get("auth_username", ""))
        with st.sidebar:
            st.caption(f"Angemeldet als {username}")
            if st.button("Abmelden", key="comparison_logout"):
                st.session_state.pop("authenticated", None)
                st.session_state.pop("auth_username", None)
                st.rerun()
        return username

    st.title("TraidSim")
    st.caption("Bitte anmelden, um den Strategievergleich zu verwenden.")
    with st.form("comparison_login_form"):
        username = st.text_input("Benutzername")
        password = st.text_input("Passwort", type="password")
        submitted = st.form_submit_button("Anmelden", type="primary")

    if submitted:
        expected_hash = str(users.get(username, ""))
        if expected_hash and _password_matches(password, expected_hash):
            st.session_state["authenticated"] = True
            st.session_state["auth_username"] = username
            st.rerun()
        st.error("Benutzername oder Passwort ist falsch.")
    st.stop()


@st.cache_data(ttl=3600, show_spinner=False)
def _load_market_data(symbol: str, period: str, interval: str) -> pd.DataFrame:
    return download_data(symbol, period=period, interval=interval)


def _eur(value: float) -> str:
    return f"{value:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(value: float) -> str:
    return f"{value:.2f} %".replace(".", ",")


def _metric_table(*results) -> pd.DataFrame:
    rows = []
    for result in results:
        metrics = result.metrics
        rows.append(
            {
                "Variante": metrics.get("Variante", ""),
                "Startkapital": metrics.get("Startkapital", 0.0),
                "Endkapital": metrics.get("Endkapital", 0.0),
                "Rendite %": metrics.get("Gesamtrendite %", 0.0),
                "Max. Drawdown %": metrics.get("Max. Drawdown %", 0.0),
                "Trades": metrics.get("Abgeschlossene Trades", 0),
                "Gebuehren": metrics.get("Gebuehren gesamt", 0.0),
                "Marktzeit %": metrics.get("Marktzeit %", 0.0),
            }
        )
    return pd.DataFrame(rows)


username = _require_login()

st.title("Strategievergleich")
st.caption(
    "Vergleicht die gewaehlte TraidSim-Strategie im selben Zeitfenster mit Buy and Hold und einem "
    "rueckblickend optimalen Long-only-Oracle. Die Funktion steht allen eingerichteten Benutzern zur Verfuegung."
)
st.warning(
    "Das Oracle kennt alle spaeteren Schlusskurse. Es ist eine theoretische Vergleichsgrenze und keine real handelbare Strategie."
)

with st.sidebar:
    st.header("Vergleichseinstellungen")
    symbol = st.text_input("Symbol", value="AAPL", key=f"comparison_symbol_{username}").strip().upper()
    period = st.selectbox("Datenzeitraum", ["6mo", "1y", "2y", "5y", "10y", "max"], index=3)
    interval = st.selectbox("Intervall", ["1d", "1wk", "1mo"], index=0)
    initial_capital = st.number_input("Startkapital", min_value=100.0, value=10_000.0, step=500.0)
    trading_fee = st.slider("Gebuehr pro Order", min_value=0.0, max_value=0.01, value=0.001, step=0.0005)
    position_mode_label = st.radio(
        "Vergleichsmodus",
        ["Realistische Positionsgroesse", "100-%-Kapitalvergleich"],
        help=(
            "Realistisch nutzt Risiko und ATR fuer die Positionsgroesse. Der 100-%-Modus investiert bei jedem Signal "
            "das gesamte verfuegbare Kapital und isoliert damit die Qualitaet der Ein- und Ausstiegssignale."
        ),
    )
    position_mode = "risk" if position_mode_label == "Realistische Positionsgroesse" else "full_capital"
    risk_per_trade = st.slider("Risiko pro Trade", 0.0025, 0.05, 0.01, 0.0025, disabled=position_mode == "full_capital")
    atr_stop = st.slider("ATR Stop-Loss Faktor", 0.5, 5.0, 2.0, 0.25)
    atr_take_profit = st.slider("ATR Take-Profit Faktor", 0.5, 8.0, 3.0, 0.25)

if not symbol:
    st.info("Bitte ein Symbol eingeben.")
    st.stop()

try:
    with st.spinner(f"Lade Kursdaten fuer {symbol} ..."):
        raw_df = _load_market_data(symbol, period, interval)
        analyzed_df = generate_signals(add_indicators(raw_df))
except Exception as exc:
    st.error(f"Kursdaten konnten nicht geladen werden: {exc}")
    st.stop()

if analyzed_df.empty:
    st.error("Keine Kursdaten vorhanden.")
    st.stop()

available_dates = pd.to_datetime(analyzed_df["Date"]).dt.date
min_date = available_dates.min()
max_date = available_dates.max()

st.subheader("1. Zeitfenster")
date_col1, date_col2 = st.columns(2)
start_date = date_col1.date_input(
    "Startdatum",
    value=min_date,
    min_value=min_date,
    max_value=max_date,
    key=f"comparison_start_{username}_{symbol}",
)
end_date = date_col2.date_input(
    "Enddatum",
    value=max_date,
    min_value=min_date,
    max_value=max_date,
    key=f"comparison_end_{username}_{symbol}",
)

if start_date > end_date:
    st.error("Das Startdatum muss vor dem Enddatum liegen.")
    st.stop()

source_df = analyzed_df[
    (pd.to_datetime(analyzed_df["Date"]).dt.date >= start_date)
    & (pd.to_datetime(analyzed_df["Date"]).dt.date <= end_date)
].copy()

st.caption(f"Zeitfenster: {start_date} bis {end_date} mit {len(source_df)} Kurszeilen und Intervall {interval}.")
if len(source_df) < 2:
    st.info("Das Zeitfenster enthaelt zu wenig Daten fuer einen Vergleich.")
    st.stop()

st.subheader("2. Kriterien")
enabled_criteria: list[str] = []
criterion_columns = st.columns(3)
for index, criterion in enumerate(CRITERIA):
    with criterion_columns[index % 3]:
        enabled = st.checkbox(
            criterion.name,
            value=True,
            key=f"comparison_criterion_{username}_{symbol}_{criterion.criterion_id}",
        )
    if enabled:
        enabled_criteria.append(criterion.criterion_id)

if not enabled_criteria:
    st.warning("Mindestens ein Kriterium muss aktiv sein.")
    st.stop()

simulation_df = apply_enabled_criteria_signals(source_df, enabled_criteria)
strategy_result = run_strategy_benchmark(
    simulation_df,
    initial_capital=initial_capital,
    risk_per_trade=risk_per_trade,
    atr_stop_factor=atr_stop,
    atr_take_profit_factor=atr_take_profit,
    trading_fee=trading_fee,
    position_mode=position_mode,
)
buy_hold_result = run_buy_and_hold_benchmark(source_df, initial_capital=initial_capital, trading_fee=trading_fee)
oracle_result = run_oracle_benchmark(source_df, initial_capital=initial_capital, trading_fee=trading_fee)
aligned = align_equity_curves(strategy_result, buy_hold_result, oracle_result)
comparison = comparison_metrics(strategy_result, buy_hold_result, oracle_result, initial_capital)

st.subheader("3. Ergebnis")
metric_col1, metric_col2, metric_col3, metric_col4, metric_col5 = st.columns(5)
metric_col1.metric("Strategie-Endkapital", _eur(float(strategy_result.metrics["Endkapital"])))
metric_col2.metric("Buy-and-Hold-Endkapital", _eur(float(buy_hold_result.metrics["Endkapital"])))
metric_col3.metric(
    "Vorteil Strategie",
    _eur(comparison["Vorteil Strategie EUR"]),
    delta=_pct(comparison["Vorteil Strategie %"]),
)
metric_col4.metric("Oracle-Endkapital", _eur(float(oracle_result.metrics["Endkapital"])))
metric_col5.metric("Erreichtes Potenzial", _pct(comparison["Erreichtes theoretisches Potenzial %"]))

comparison_tab, oracle_tab, trades_tab = st.tabs(["Strategie vs. Buy and Hold", "Theoretisches Optimum", "Trades und Kennzahlen"])

with comparison_tab:
    st.plotly_chart(make_strategy_vs_buy_hold_chart(aligned, symbol), use_container_width=True)
    if comparison["Vorteil Strategie EUR"] >= 0:
        st.success(
            f"Die Strategie liegt am Ende um {_eur(comparison['Vorteil Strategie EUR'])} "
            f"beziehungsweise {_pct(comparison['Vorteil Strategie %'])} vor Buy and Hold."
        )
    else:
        st.error(
            f"Die Strategie liegt am Ende um {_eur(abs(comparison['Vorteil Strategie EUR']))} "
            f"hinter Buy and Hold."
        )

with oracle_tab:
    logarithmic = st.checkbox("Logarithmische Y-Achse", value=False, key=f"comparison_log_{username}_{symbol}")
    st.plotly_chart(make_oracle_comparison_chart(aligned, symbol, logarithmic), use_container_width=True)
    st.plotly_chart(make_oracle_trade_chart(source_df, oracle_result.trades, symbol), use_container_width=True)
    st.caption(
        "Oracle-Regel: maximal eine Long-Position, kein Hebel, kein Shorting, jeweils das gesamte Kapital, "
        "Kauf und Verkauf auf Schlusskursbasis, Gebuehren bei jeder Order."
    )
    st.metric("Abstand der Strategie zum Oracle", _eur(comparison["Abstand zum Oracle EUR"]), _pct(comparison["Abstand zum Oracle %"]))

with trades_tab:
    st.write("### Kennzahlen")
    metrics_df = _metric_table(strategy_result, buy_hold_result, oracle_result)
    st.dataframe(
        metrics_df.style.format(
            {
                "Startkapital": lambda value: _eur(float(value)),
                "Endkapital": lambda value: _eur(float(value)),
                "Rendite %": lambda value: _pct(float(value)),
                "Max. Drawdown %": lambda value: _pct(float(value)),
                "Gebuehren": lambda value: _eur(float(value)),
                "Marktzeit %": lambda value: _pct(float(value)),
            }
        ),
        use_container_width=True,
    )

    strategy_trade_tab, oracle_trade_tab, buy_hold_trade_tab = st.tabs(["Strategie-Trades", "Oracle-Trades", "Buy-and-Hold-Trades"])
    with strategy_trade_tab:
        if strategy_result.trades.empty:
            st.info("Keine Strategie-Trades im gewaehlten Zeitfenster.")
        else:
            st.dataframe(strategy_result.trades, use_container_width=True)
            st.download_button(
                "Strategie-Trades als CSV",
                strategy_result.trades.to_csv(index=False).encode("utf-8"),
                f"{symbol}_strategie_trades.csv",
                "text/csv",
            )
    with oracle_trade_tab:
        if oracle_result.trades.empty:
            st.info("Das Oracle bleibt in diesem Zeitfenster vollstaendig in Cash.")
        else:
            st.dataframe(oracle_result.trades, use_container_width=True)
            st.download_button(
                "Oracle-Trades als CSV",
                oracle_result.trades.to_csv(index=False).encode("utf-8"),
                f"{symbol}_oracle_trades.csv",
                "text/csv",
            )
    with buy_hold_trade_tab:
        st.dataframe(buy_hold_result.trades, use_container_width=True)

    st.download_button(
        "Kapitalverlaeufe als CSV",
        aligned.to_csv(index=False).encode("utf-8"),
        f"{symbol}_strategie_vergleich.csv",
        "text/csv",
    )
