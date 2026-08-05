from __future__ import annotations

import hashlib
import hmac
import importlib
import base64
import json
import secrets
import time
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from src.backtest import backtest, buy_and_hold_metrics, calculate_metrics
from src.data_provider import download_data
from src.daytrading_monitor import analyze_intraday, simulate_current_day
from src.paper_trading import PaperAccount, open_virtual_position, process_virtual_order
from src.indicators import IndicatorParameters, add_indicators
from src.monte_carlo import MonteCarloConfig, run_monte_carlo_robustness
from src.scoring import signal_history_payload, strategy_score
from src.storage import (
    create_alert_if_buy,
    list_analysis_results,
    list_watchlists,
    load_analysis_result,
    recent_alerts,
    recent_signal_history,
    save_analysis_result,
    save_signal_history,
    save_watchlist,
)
from src.strategy import StrategyParameters, generate_signals
from src import charts as charts_module
from src import hyperopt as hyperopt_module
from src import hyperopt2 as hyperopt2_module
from src import telemetry as telemetry_module
from src import i18n as i18n_module
from src.documentation import DOCUMENTATION


charts_module = importlib.reload(charts_module)
hyperopt_module = importlib.reload(hyperopt_module)
hyperopt2_module = importlib.reload(hyperopt2_module)
telemetry_module = importlib.reload(telemetry_module)
i18n_module = importlib.reload(i18n_module)
localize_phrase = i18n_module.localize_phrase
parameter_label = i18n_module.parameter_label
translate = i18n_module.translate
make_candlestick_chart = charts_module.make_candlestick_chart
make_chart = charts_module.make_chart
make_equity_chart = charts_module.make_equity_chart
best_hyperopt_parameters = hyperopt_module.best_hyperopt_parameters
run_hyperopt = hyperopt_module.run_hyperopt
OBJECTIVES = hyperopt2_module.OBJECTIVES
best_hyperopt2_parameters = hyperopt2_module.best_parameters
recommended_criteria = hyperopt2_module.recommended_criteria
run_hyperopt2 = hyperopt2_module.run_hyperopt2
hyperopt2_result_to_payload = hyperopt2_module.result_to_payload
hyperopt2_result_from_payload = hyperopt2_module.result_from_payload
CRITERIA = telemetry_module.CRITERIA
apply_enabled_criteria_signals = telemetry_module.apply_enabled_criteria_signals
build_criterion_telemetry = telemetry_module.build_criterion_telemetry


APP_DIR = Path(__file__).parent
LOGO_PATH = APP_DIR / "assets" / "traidsim_logo.png"


st.set_page_config(page_title="DayTrade Lab", page_icon="chart_with_upwards_trend", layout="wide")


@st.cache_resource
def language_handoff_tokens() -> dict[str, tuple[str, float]]:
    return {}


def create_language_handoff(username: str) -> str:
    tokens = language_handoff_tokens()
    now = time.time()
    expired = [token for token, (_, expiry) in tokens.items() if expiry < now]
    for token in expired:
        tokens.pop(token, None)
    token = secrets.token_urlsafe(24)
    tokens[token] = (username, now + 120.0)
    return token


def consume_language_handoff(token: str) -> str | None:
    record = language_handoff_tokens().pop(token, None)
    if record is None:
        return None
    username, expiry = record
    return username if expiry >= time.time() else None


def get_auth_config() -> dict:
    try:
        return dict(st.secrets.get("auth", {}))
    except Exception:
        return {}


def password_matches(password: str, password_hash: str) -> bool:
    entered_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(entered_hash, password_hash)


def logo_data_uri() -> str:
    encoded = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def require_login() -> None:
    auth_language = str(st.query_params.get("lang", "de"))
    if auth_language not in {"de", "en", "ru"}:
        auth_language = "de"
    auth_tr = lambda key, **values: translate(key, auth_language).format(**values)
    auth_config = get_auth_config()
    users = dict(auth_config.get("users", {}))
    if not users and auth_config.get("username") and auth_config.get("password_sha256"):
        users = {str(auth_config["username"]): str(auth_config["password_sha256"])}

    if not users:
        st.error("Login ist nicht eingerichtet. Bitte .streamlit/secrets.toml mit Benutzer und Passwort-Hash anlegen.")
        st.stop()

    handoff_token = str(st.query_params.get("auth_handoff", ""))
    if handoff_token and not st.session_state.get("authenticated"):
        handoff_username = consume_language_handoff(handoff_token)
        if handoff_username in users:
            st.session_state["authenticated"] = True
            st.session_state["auth_username"] = handoff_username
        st.query_params.pop("auth_handoff", None)

    if st.session_state.get("authenticated"):
        with st.sidebar:
            st.caption(auth_tr("logged_in_as", user=st.session_state.get("auth_username", "")))
            if st.button(auth_tr("logout")):
                st.session_state.pop("authenticated", None)
                st.session_state.pop("auth_username", None)
                st.session_state.pop("login_defaults_applied_for", None)
                st.rerun()
        return

    st.markdown(
        """
        <style>
        [data-testid="stAppViewContainer"] .main .block-container {
            padding-top: max(3rem, calc(50vh - 165px));
            padding-bottom: 2rem;
        }
        [data-testid="stForm"] {
            padding: 1.1rem 1.1rem 0.9rem 1.1rem;
        }
        [data-testid="stForm"] label {
            font-size: 0.85rem;
        }
        [data-testid="stForm"] input {
            min-height: 2.35rem;
        }
        [data-testid="stFormSubmitButton"] button {
            width: 100%;
        }
        h1 {
            font-size: 2rem !important;
            margin-bottom: 0.2rem !important;
        }
        .login-brand {
            text-align: center;
        }
        .login-logo img {
            width: 100%;
            max-width: 240px;
            height: auto;
            margin: 0 auto 1rem auto;
            display: block;
        }
        .brand-traid {
            color: #22c55e;
        }
        .brand-sim {
            color: #ef4444;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    left_space, login_column, right_space = st.columns([1, 0.42, 1])
    with login_column:
        st.markdown(f"<div class='login-logo'><img src='{logo_data_uri()}' alt='TraidSim'></div>", unsafe_allow_html=True)
        st.caption(auth_tr("login_required"))
        with st.form("login_form"):
            username = st.text_input(auth_tr("username"))
            password = st.text_input(auth_tr("password"), type="password")
            submitted = st.form_submit_button(auth_tr("login"), type="primary")
        st.caption(auth_tr("forgot_password"))

    if submitted:
        expected_password_hash = str(users.get(username, ""))
        if expected_password_hash and password_matches(password, expected_password_hash):
            st.session_state["authenticated"] = True
            st.session_state["auth_username"] = username
            st.rerun()
        st.error(auth_tr("bad_login"))

    st.stop()


require_login()

DISCLAIMER = """
Dies ist ein technisches Analyse- und Backtesting-Tool. Es handelt sich nicht um Anlageberatung.
Die Signale sind regelbasierte technische Auswertungen und keine persoenliche Kauf- oder Verkaufsempfehlung.
"""

DEFAULT_WATCHLIST = "AAPL,AMZN,NVDA,MSFT,GOOGL,BTC-USDT,ETH-USDT,SOL-USDT,1211.HK"


def parse_symbols(raw_symbols: str) -> list[str]:
    return [symbol.strip().upper() for symbol in raw_symbols.split(",") if symbol.strip()]


def tradingview_symbol(symbol: str) -> str:
    """Uebersetzt die gaengigsten Watchlist-Symbole fuer TradingView."""
    normalized = symbol.upper().strip()
    if normalized.endswith("-USDT"):
        return f"BINANCE:{normalized.replace('-', '')}"
    if normalized.endswith("-USD"):
        return f"COINBASE:{normalized.replace('-', '')}"
    if normalized.endswith(".HK"):
        return f"HKEX:{normalized.removesuffix('.HK')}"
    if normalized == "^GDAXI":
        return "XETR:DAX"
    return f"NASDAQ:{normalized}"


def render_tradingview_chart(symbol: str) -> None:
    widget_config = {
        "autosize": False,
        "width": "100%",
        "height": 850,
        "symbol": tradingview_symbol(symbol),
        "interval": "15",
        "timezone": "Europe/Berlin",
        "theme": "dark",
        "style": "1",
        "locale": "de_DE",
        "allow_symbol_change": True,
        "hide_side_toolbar": False,
        "withdateranges": True,
        "details": True,
        "calendar": False,
        "support_host": "https://www.tradingview.com",
    }
    components.html(
        f"""
        <style>
          html, body {{ height: 100%; margin: 0; overflow: hidden; }}
          .tradingview-widget-container,
          .tradingview-widget-container__widget {{ height: 850px !important; width: 100% !important; }}
          .tradingview-widget-container iframe {{ height: 850px !important; min-height: 850px !important; }}
        </style>
        <div class="tradingview-widget-container">
          <div class="tradingview-widget-container__widget"></div>
          <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
          {json.dumps(widget_config)}
          </script>
        </div>
        """,
        height=900,
        scrolling=False,
    )


@st.cache_data(ttl=60, show_spinner=False)
def load_intraday_monitor_data(symbol: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return (
        download_data(symbol, period="3mo", interval="60m"),
        download_data(symbol, period="1mo", interval="15m"),
        download_data(symbol, period="5d", interval="5m"),
    )


@st.fragment(run_every="60s")
def render_daytrading_monitor(
    symbol: str, initial_capital: float, trade_amount: float, risk_per_trade: float,
    fee: float, atr_stop: float, atr_tp: float, automatic_paper_trading: bool,
) -> None:
    st.subheader("Daytrading-Monitor")
    st.caption("1 Stunde = Trend · 15 Minuten = Handelssignal · 5 Minuten = Einstieg · Aktualisierung höchstens einmal pro Minute")
    try:
        hourly, fifteen_minute, five_minute = load_intraday_monitor_data(symbol)
        monitor = analyze_intraday(hourly, fifteen_minute, five_minute)
        day_curve = simulate_current_day(five_minute, trade_amount, fee)
    except Exception as exc:
        st.warning(f"Intraday-Monitor konnte noch keine Daten laden: {exc}")
        return

    st.markdown(
        f"""
        <div style="padding:1.25rem 1.4rem;border-radius:0.8rem;background:{monitor['color']};color:white;margin:0.5rem 0 1rem 0">
          <div style="font-size:0.82rem;opacity:0.88">AKTUELLES MONITOR-SIGNAL</div>
          <div style="font-size:2rem;font-weight:800;line-height:1.2">{monitor['signal']}</div>
          <div style="margin-top:0.35rem">{monitor['reason']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if "paper_account" not in st.session_state:
        st.session_state["paper_account"] = PaperAccount.create(initial_capital)
    account: PaperAccount = st.session_state["paper_account"]
    manual_opened = False
    if account.quantity == 0 and st.button("Einsatzsumme jetzt virtuell kaufen", type="primary"):
        result = open_virtual_position(
            account,
            symbol=symbol,
            price=monitor["price"],
            atr=monitor["values"]["5m"]["ATR"],
            trade_amount=trade_amount,
            fee_fraction=fee,
            stop_factor=atr_stop,
            take_profit_factor=atr_tp,
        )
        st.success(result)
        manual_opened = account.quantity > 0
    order_result = "Virtuelle Startposition angelegt" if manual_opened else "Automatik pausiert"
    if automatic_paper_trading and not manual_opened:
        order_result = process_virtual_order(
            account,
            symbol=symbol,
            signal=monitor["signal"],
            price=monitor["price"],
            atr=monitor["values"]["5m"]["ATR"],
            candle_id=f"{symbol}:{monitor['updated_at']}",
            trade_amount=trade_amount,
            risk_fraction=risk_per_trade,
            fee_fraction=fee,
            stop_factor=atr_stop,
            take_profit_factor=atr_tp,
        )

    st.write("#### Automatisches virtuelles Depot")
    paper_columns = st.columns(7)
    paper_columns[0].metric("Status", "AKTIV" if automatic_paper_trading else "PAUSIERT")
    valuation_price = monitor["price"] if account.symbol in {None, symbol} else account.entry_price
    paper_columns[1].metric("Virtuelles Kapital", f"{account.equity(valuation_price):,.2f} €")
    paper_columns[2].metric("Cash", f"{account.cash:,.2f} €")
    paper_columns[3].metric("Position", f"{account.quantity} Stück")
    paper_columns[4].metric("Einstieg", f"{account.entry_price:.2f}" if account.quantity else "–")
    paper_columns[5].metric("Stop-Loss", f"{account.stop_price:.2f}" if account.quantity else "–")
    paper_columns[6].metric("Take-Profit", f"{account.take_profit_price:.2f}" if account.quantity else "–")
    st.caption(f"Letzte Automatikaktion: {order_result}")
    if account.trades:
        st.dataframe(pd.DataFrame(account.trades[-20:][::-1]), use_container_width=True, hide_index=True)

    metric_columns = st.columns(6)
    metric_columns[0].metric("Einsatz", f"{trade_amount:,.0f} €")
    metric_columns[1].metric("Risikobudget", f"{trade_amount * risk_per_trade:,.2f} €")
    metric_columns[2].metric("Kurs", f"{monitor['price']:.2f}")
    metric_columns[3].metric("1h-Trend", monitor["trend_1h"])
    metric_columns[4].metric("15m-Bestätigungen", f"{monitor['confirmation_count']}/4")
    metric_columns[5].metric("5m-Einstieg", "Bereit" if monitor["entry_5m"] else "Warten")

    values = monitor["values"]
    hour_rows = [
        {"Kriterium": "Kurs über SMA 50", "Aktuell": values["1h"]["Kurs"], "Vergleich": values["1h"]["SMA 50"], "Status": "Erfüllt" if values["1h"]["Kurs"] > values["1h"]["SMA 50"] else "Nicht erfüllt"},
        {"Kriterium": "SMA 20 über SMA 50", "Aktuell": values["1h"]["SMA 20"], "Vergleich": values["1h"]["SMA 50"], "Status": "Erfüllt" if values["1h"]["SMA 20"] > values["1h"]["SMA 50"] else "Nicht erfüllt"},
    ]
    setup_rows = [
        {"Kriterium": "RSI zwischen 40 und 65", "Aktuell": values["15m"]["RSI"], "Vergleich": "40–65", "Status": "Erfüllt" if monitor["confirmations"]["RSI 40–65"] else "Nicht erfüllt"},
        {"Kriterium": "MACD über Signallinie", "Aktuell": values["15m"]["MACD"], "Vergleich": values["15m"]["MACD-Signallinie"], "Status": "Erfüllt" if monitor["confirmations"]["MACD bullisch"] else "Nicht erfüllt"},
        {"Kriterium": "Kurs über Bollinger-Mitte", "Aktuell": values["15m"]["Kurs"], "Vergleich": values["15m"]["Bollinger-Mitte"], "Status": "Erfüllt" if monitor["confirmations"]["Über Bollinger-Mitte"] else "Nicht erfüllt"},
        {"Kriterium": "Volumen über Durchschnitt", "Aktuell": values["15m"]["Volumen"], "Vergleich": values["15m"]["Volumen-SMA 20"], "Status": "Erfüllt" if monitor["confirmations"]["Volumen bestätigt"] else "Nicht erfüllt"},
    ]
    entry_rows = [
        {"Kriterium": "Kurs über SMA 20", "Aktuell": values["5m"]["Kurs"], "Vergleich": values["5m"]["SMA 20"], "Status": "Erfüllt" if values["5m"]["Kurs"] > values["5m"]["SMA 20"] else "Nicht erfüllt"},
        {"Kriterium": "MACD über Signallinie", "Aktuell": values["5m"]["MACD"], "Vergleich": values["5m"]["MACD-Signallinie"], "Status": "Erfüllt" if values["5m"]["MACD"] > values["5m"]["MACD-Signallinie"] else "Nicht erfüllt"},
    ]

    def colored_criteria(rows: list[dict]) -> pd.io.formats.style.Styler:
        frame = pd.DataFrame(rows)
        return frame.style.apply(
            lambda row: [
                "background-color: rgba(22, 163, 74, 0.32); color: #dcfce7; font-weight: 600"
                if row["Status"] == "Erfüllt"
                else "background-color: rgba(220, 38, 38, 0.32); color: #fee2e2; font-weight: 600"
            ] * len(row),
            axis=1,
        )

    hour_column, setup_column, entry_column = st.columns(3, gap="medium")
    with hour_column:
        st.write("#### 1 Stunde – Trend")
        st.dataframe(colored_criteria(hour_rows), use_container_width=True, hide_index=True, height=178)
    with setup_column:
        st.write("#### 15 Minuten – Signal")
        st.dataframe(colored_criteria(setup_rows), use_container_width=True, hide_index=True, height=178)
    with entry_column:
        st.write("#### 5 Minuten – Einstieg")
        st.dataframe(colored_criteria(entry_rows), use_container_width=True, hide_index=True, height=178)
    st.caption(f"Letzte verfügbare 5-Minuten-Kerze: {monitor['updated_at']} · automatische Aktualisierung alle 60 Sekunden")

    last_profit = float(day_curve["Gewinn"].iloc[-1])
    profit_color = "#16a34a" if last_profit >= 0 else "#dc2626"
    figure = go.Figure()
    figure.add_trace(go.Scatter(
        x=day_curve["Date"], y=day_curve["Gewinn"], mode="lines",
        name="Simulierter Tagesgewinn", line={"color": profit_color, "width": 3},
        fill="tozeroy",
    ))
    figure.add_hline(y=0, line_dash="dash", line_color="#94a3b8")
    figure.update_layout(
        title=f"Simulierter Gewinn heute: {last_profit:,.2f} €",
        height=460, xaxis_title="Uhrzeit", yaxis_title="Gewinn / Verlust in €",
        hovermode="x unified", margin={"l": 30, "r": 20, "t": 60, "b": 30},
        paper_bgcolor="#0b0b0b", plot_bgcolor="#0b0b0b", font={"color": "#f2f2f2"},
    )
    st.plotly_chart(figure, use_container_width=True)
    st.caption("Die Gewinnkurve ist eine rückblickende Intraday-Simulation auf 5-Minuten-Kerzen mit dem gewählten Einsatz und den eingestellten Gebühren. Das Risikobudget dient als Vorgabe für die spätere Stop-/Positionsgrößenberechnung. Sie ist keine reale oder garantierte Rendite.")


def format_metrics(metrics: dict) -> pd.DataFrame:
    return pd.DataFrame([{key: round(value, 2) if isinstance(value, float) else value for key, value in metrics.items()}])


def format_hyperopt_value(value):
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return round(value, 4)
    return value


def calculate_parameter_influences(results_df: pd.DataFrame) -> dict[str, float]:
    if results_df.empty or "Objective" not in results_df.columns:
        return {}

    penalty_limit = -999_000
    valid = results_df[results_df["Objective"] > penalty_limit].copy()
    if len(valid) < 2:
        return {}

    ignored_columns = {
        "Durchlauf",
        "Objective",
        "Startkapital",
        "Endkapital",
        "Gesamtrendite %",
        "Max. Drawdown %",
        "Abgeschlossene Trades",
        "Trefferquote %",
        "Gewinnsumme",
        "Durchschnitt Trade",
        "Bester Trade",
        "Schlechtester Trade",
    }
    raw_scores = {}
    for column in valid.columns:
        if column in ignored_columns or valid[column].nunique(dropna=True) < 2:
            continue
        grouped_objective = valid.groupby(column, dropna=True)["Objective"].mean()
        if len(grouped_objective) < 2:
            continue
        raw_scores[column] = float(grouped_objective.max() - grouped_objective.min())

    max_score = max(raw_scores.values(), default=0.0)
    if max_score <= 0:
        return {}
    return {column: score / max_score * 100 for column, score in raw_scores.items()}


def influence_label(score: float) -> str:
    if score >= 67:
        return "hoch"
    if score >= 34:
        return "mittel"
    return "gering"


def influence_color(score: float) -> str:
    score = max(0.0, min(100.0, float(score)))
    red = (239, 68, 68)
    amber = (245, 158, 11)
    green = (34, 197, 94)
    if score <= 50:
        start, end, ratio = red, amber, score / 50
    else:
        start, end, ratio = amber, green, (score - 50) / 50
    rgb = tuple(round(start[index] + (end[index] - start[index]) * ratio) for index in range(3))
    return f"background-color: rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, 0.35); color: #f8fafc; font-weight: 700;"


def style_hyperopt_parameter_row(row: pd.Series) -> list[str]:
    score = float(row.get("Einfluss %", 0.0))
    style = influence_color(score)
    return [style if column in {"Einfluss %", "Wichtigkeit"} else "" for column in row.index]


def hyperopt_parameter_rows(
    best_params,
    enabled_criteria: dict[str, bool],
    results_df: pd.DataFrame | None = None,
) -> list[dict]:
    row_definitions = [
        ("trend", "SMA Trend positiv", "Trendfilter-Periode", "sma_trend_period"),
        ("rsi", "RSI im Zielbereich", "RSI-Periode", "rsi_period"),
        ("rsi", "RSI im Zielbereich", "Kaufschwelle unten", "rsi_min"),
        ("rsi", "RSI im Zielbereich", "Verkaufsschwelle oben", "rsi_max"),
        ("rsi", "RSI Exit", "Exit RSI", "exit_rsi_max"),
        ("macd", "MACD bullisch", "Schnelle EMA", "macd_fast"),
        ("macd", "MACD bullisch", "Langsame EMA", "macd_slow"),
        ("macd", "MACD bullisch", "Signal-EMA", "macd_signal"),
        ("bollinger", "Bollinger Momentum positiv", "Periode", "bb_period"),
        ("bollinger", "Bollinger Momentum positiv", "Standardabweichungen", "bb_std"),
        ("fibonacci", "Fibonacci Unterstuetzung haelt", "Lookback Kerzen", "fib_lookback"),
        ("volume", "Volumen bestaetigt", "Durchschnitts-Periode", "volume_period"),
        ("volume", "Volumen bestaetigt", "Mindest-Vielfaches", "volume_factor"),
        ("stoch", "Stochastik positiv", "Periode", "stoch_period"),
        ("stoch", "Stochastik positiv", "Glaettung %D", "stoch_signal"),
        ("stoch", "Stochastik positiv", "Kaufschwelle unten", "stoch_min"),
        ("stoch", "Stochastik positiv", "Verkaufsschwelle oben", "stoch_max"),
        ("atr", "ATR Volatilitaet handelbar", "Periode", "atr_period"),
        ("atr", "ATR Volatilitaet handelbar", "Min. ATR % vom Kurs", "atr_min_pct"),
        ("atr", "ATR Volatilitaet handelbar", "Max. ATR % vom Kurs", "atr_max_pct"),
        ("ichimoku", "Ichimoku bullisch", "Tenkan-Periode", "ichimoku_tenkan"),
        ("ichimoku", "Ichimoku bullisch", "Kijun-Periode", "ichimoku_kijun"),
        ("ichimoku", "Ichimoku bullisch", "Senkou-B-Periode", "ichimoku_senkou_b"),
        ("risk_management", "Risikomanagement", "Risiko je Trade", "risk_per_trade"),
        ("risk_management", "Risikomanagement", "ATR Stop-Faktor", "atr_stop_factor"),
        ("risk_management", "Risikomanagement", "ATR Take-Profit-Faktor", "atr_take_profit_factor"),
    ]

    influences = calculate_parameter_influences(results_df) if results_df is not None else {}
    rows = []
    for criterion_key, area, parameter, attribute in row_definitions:
        if criterion_key is not None and not enabled_criteria.get(criterion_key, False):
            continue
        influence = round(influences.get(attribute, 0.0), 0)
        rows.append(
            {
                "Bereich": area,
                "Parameter": parameter,
                "Hyperopt-Wert": format_hyperopt_value(getattr(best_params, attribute)),
                "Einfluss %": influence,
                "Wichtigkeit": influence_label(influence),
            }
        )
    return rows


def make_hyperopt_convergence_chart(results_df: pd.DataFrame, symbol: str, optimizer_name: str = "Hyperopt"):
    ordered = results_df.sort_values("Durchlauf").copy() if "Durchlauf" in results_df.columns else results_df.sort_index().copy()
    if "Durchlauf" not in ordered.columns:
        ordered["Durchlauf"] = range(1, len(ordered) + 1)

    penalty_limit = -999_000
    valid = ordered[ordered["Objective"] > penalty_limit].copy()
    invalid_count = len(ordered) - len(valid)

    fig = go.Figure()

    if not valid.empty:
        valid["Bester Objective"] = valid["Objective"].cummax()
        final_best = float(valid["Bester Objective"].iloc[-1])
        first_best = float(valid["Bester Objective"].iloc[0])
        denominator = abs(final_best - first_best)
        if denominator < 0.000001:
            valid["Abstand zur Loesung %"] = 0.0
        else:
            valid["Abstand zur Loesung %"] = (final_best - valid["Bester Objective"]) / denominator * 100

        improvements = valid[valid["Bester Objective"] > valid["Bester Objective"].shift(1).fillna(float("-inf"))]
        solution_trial = int(valid[valid["Bester Objective"] == final_best]["Durchlauf"].iloc[0])

        fig.add_trace(
            go.Scatter(
                x=valid["Durchlauf"],
                y=valid["Abstand zur Loesung %"],
                mode="lines",
                name="Abstand zur besten Loesung",
                line={"color": "#f97316", "width": 3},
                hovertemplate="Durchlauf %{x}<br>Abstand %{y:.1f}%<extra></extra>",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=improvements["Durchlauf"],
                y=improvements["Abstand zur Loesung %"],
                mode="markers",
                name="Neue beste Loesung",
                marker={"size": 10, "color": "#22c55e", "symbol": "diamond"},
                hovertemplate="Durchlauf %{x}<br>neuer Bestwert<br>Abstand %{y:.1f}%<extra></extra>",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=valid["Durchlauf"],
                y=valid["Bester Objective"],
                mode="lines",
                name="Bester Objective",
                yaxis="y2",
                line={"color": "#38bdf8", "width": 2, "dash": "dot"},
                hovertemplate="Durchlauf %{x}<br>Bester Objective %{y:.2f}<extra></extra>",
            )
        )
        fig.add_annotation(
            text=f"Beste Loesung gefunden ab Durchlauf {solution_trial}",
            x=solution_trial,
            y=0,
            xref="x",
            yref="y",
            showarrow=True,
            arrowhead=2,
            ax=40,
            ay=-45,
            font={"size": 13, "color": "#22c55e"},
        )
    else:
        fig.add_annotation(
            text="Keine gueltigen Durchlaeufe. Mindest-Trades senken oder Filter lockern.",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font={"size": 16, "color": "#f87171"},
        )

    fig.add_annotation(
        text=f"Gueltig: {len(valid)} / {len(ordered)} | Bestraft wegen Mindest-Trades: {invalid_count}",
        x=0,
        y=1.12,
        xref="paper",
        yref="paper",
        showarrow=False,
        align="left",
        font={"size": 13, "color": "#e5e7eb"},
    )
    fig.update_layout(
        title=f"{symbol} - {optimizer_name} Konvergenz zur besten Loesung",
        height=430,
        xaxis_title="Durchlauf",
        yaxis={
            "title": "Abstand zur besten Loesung",
            "ticksuffix": "%",
            "range": [105, -5],
        },
        yaxis2={
            "title": "Bester Objective",
            "overlaying": "y",
            "side": "right",
            "showgrid": False,
        },
        legend={"orientation": "h"},
    )
    return fig


def make_monte_carlo_paths_chart(paths_df: pd.DataFrame, symbol: str):
    fig = go.Figure()
    if paths_df.empty:
        fig.update_layout(title=f"{symbol} - Monte Carlo Zukunftspfade", height=420)
        return fig

    for path_id, path_df in paths_df.groupby("Pfad"):
        fig.add_trace(
            go.Scatter(
                x=path_df["Tag"],
                y=path_df["Close"],
                mode="lines",
                name=f"Pfad {path_id}",
                line={"color": "rgba(148, 163, 184, 0.22)", "width": 1},
                showlegend=False,
                hovertemplate="Tag %{x}<br>Kurs %{y:.2f}<extra></extra>",
            )
        )

    median_path = paths_df.groupby("Tag", as_index=False)["Close"].median()
    fig.add_trace(
        go.Scatter(
            x=median_path["Tag"],
            y=median_path["Close"],
            mode="lines",
            name="Median",
            line={"color": "#22c55e", "width": 3},
            hovertemplate="Tag %{x}<br>Median %{y:.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        title=f"{symbol} - Monte Carlo Zukunftspfade fuer 1 Jahr",
        height=430,
        xaxis_title="Handelstage in der Zukunft",
        yaxis_title="Simulierter Kurs",
        legend={"orientation": "h"},
    )
    return fig


language = str(st.query_params.get("lang", "de"))
if language not in {"de", "en", "ru"}:
    language = "de"

st.markdown(
    f"""
    <style>
    html, body, .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stAppViewContainer"] > .main {{
        background-color: #000000 !important;
    }}
    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    [data-testid="stBottom"] {{
        background-color: #000000 !important;
    }}
    [data-testid="stSidebar"],
    [data-testid="stSidebarContent"] {{
        background-color: #080808 !important;
    }}
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] textarea,
    [data-testid="stSidebar"] [data-baseweb="select"] > div,
    [data-testid="stAppViewContainer"] input,
    [data-testid="stAppViewContainer"] textarea,
    [data-testid="stAppViewContainer"] [data-baseweb="select"] > div {{
        background-color: #141414 !important;
    }}
    [data-testid="stDataFrame"] {{
        background: #0f0f0f !important;
    }}
    [data-testid="stExpander"] {{
        background: #0f0f0f !important;
        border-color: #303030 !important;
    }}
    .traidsim-language-picker {{
        position: fixed;
        top: 0.55rem;
        left: 23.5rem;
        right: auto;
        z-index: 1000000;
        color: #f8fafc;
    }}
    .traidsim-language-picker summary {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.5rem;
        width: 3.7rem;
        height: 2rem;
        padding: 0.25rem 0.45rem;
        cursor: pointer;
        list-style: none;
        border-radius: 0.5rem;
        background: rgba(15, 23, 42, 0.88);
        border: 1px solid rgba(148, 163, 184, 0.25);
    }}
    .traidsim-language-picker summary::-webkit-details-marker {{ display: none; }}
    .traidsim-language-picker summary::after {{
        content: "▾";
        color: #94a3b8;
        font-size: 0.72rem;
    }}
    .traidsim-language-picker[open] summary::after {{ content: "▴"; }}
    .traidsim-language-menu {{
        position: absolute;
        top: 2.3rem;
        right: 0;
        min-width: 8.8rem;
        padding: 0.3rem;
        border-radius: 0.55rem;
        background: #111827;
        border: 1px solid rgba(148, 163, 184, 0.3);
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.35);
    }}
    .traidsim-language-menu a {{
        display: flex;
        align-items: center;
        gap: 0.55rem;
        padding: 0.42rem 0.5rem;
        border-radius: 0.35rem;
        text-decoration: none;
        color: #f8fafc;
        font-size: 0.82rem;
    }}
    .traidsim-language-menu a:hover,
    .traidsim-language-menu a[data-active="true"] {{
        background: rgba(148, 163, 184, 0.2);
    }}
    .country-flag {{
        display: inline-block;
        flex: 0 0 auto;
        width: 1.75rem;
        height: 1.08rem;
        border-radius: 0.12rem;
        box-shadow: 0 0 0 1px rgba(255,255,255,0.28);
        overflow: hidden;
    }}
    .flag-de {{
        background: linear-gradient(to bottom, #111 0 33.333%, #dd0000 33.333% 66.666%, #ffce00 66.666% 100%);
    }}
    .flag-ru {{
        background: linear-gradient(to bottom, #fff 0 33.333%, #1c57a7 33.333% 66.666%, #d52b1e 66.666% 100%);
    }}
    .flag-gb {{
        background:
            linear-gradient(to bottom, transparent 40%, #c8102e 40% 60%, transparent 60%),
            linear-gradient(to right, transparent 42%, #c8102e 42% 58%, transparent 58%),
            linear-gradient(32deg, transparent 42%, #fff 42% 47%, #c8102e 47% 53%, #fff 53% 58%, transparent 58%),
            linear-gradient(-32deg, transparent 42%, #fff 42% 47%, #c8102e 47% 53%, #fff 53% 58%, transparent 58%),
            #012169;
    }}
    @media (max-width: 900px) {{
        .traidsim-language-picker {{
            left: 4.25rem;
            right: auto;
        }}
    }}
    </style>
    <details class="traidsim-language-picker">
        <summary title="Sprache auswählen"><span class="country-flag flag-{'gb' if language == 'en' else language}"></span></summary>
        <nav class="traidsim-language-menu" aria-label="Sprachauswahl">
            <a href="?lang=de" data-active="{str(language == 'de').lower()}"><span class="country-flag flag-de"></span>Deutsch</a>
            <a href="?lang=en" data-active="{str(language == 'en').lower()}"><span class="country-flag flag-gb"></span>English</a>
            <a href="?lang=ru" data-active="{str(language == 'ru').lower()}"><span class="country-flag flag-ru"></span>Русский</a>
        </nav>
    </details>
    """,
    unsafe_allow_html=True,
)

st.title("DayTrade Lab")
st.caption("Regelbasierte Daytrading-Simulation und Strategieanalyse")
tr = lambda key, **values: translate(key, language).format(**values)


def localized_dataframe(source: pd.DataFrame) -> pd.DataFrame:
    result = source.copy()
    result = result.rename(
        columns={column: localize_phrase(parameter_label(column, language), language) for column in result.columns}
    )
    for column in result.select_dtypes(include="object").columns:
        result[column] = result[column].map(lambda value: localize_phrase(value, language))
    return result


def localized_figure(figure):
    figure.update_layout(
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font={"color": "#f8fafc"},
    )
    if language == "de":
        return figure
    if getattr(figure.layout, "title", None) and figure.layout.title.text:
        figure.layout.title.text = localize_phrase(figure.layout.title.text, language)
    for axis_name in ("xaxis", "xaxis2", "yaxis", "yaxis2"):
        axis = getattr(figure.layout, axis_name, None)
        if axis and axis.title and axis.title.text:
            axis.title.text = localize_phrase(axis.title.text, language)
    for annotation in figure.layout.annotations or []:
        if annotation.text:
            annotation.text = localize_phrase(annotation.text, language)
    for trace in figure.data:
        if getattr(trace, "name", None):
            trace.name = localize_phrase(trace.name, language)
        if getattr(trace, "hovertemplate", None):
            trace.hovertemplate = localize_phrase(trace.hovertemplate, language)
    return figure

st.caption(tr("tagline"))
st.warning(tr("disclaimer"))

saved_watchlists = list_watchlists()
saved_names = ["Manuelle Eingabe"] + [item["name"] for item in saved_watchlists]

with st.sidebar:
    st.header(tr("settings"))

    selected_watchlist = st.selectbox(tr("saved_watchlist"), saved_names, format_func=lambda value: tr("manual_entry") if value == "Manuelle Eingabe" else value)
    selected_symbols = DEFAULT_WATCHLIST
    if selected_watchlist != "Manuelle Eingabe":
        selected_symbols = next(item["symbols"] for item in saved_watchlists if item["name"] == selected_watchlist)

    watchlist_text = st.text_area(tr("watchlist_csv"), value=selected_symbols, height=120)

    watchlist_name = st.text_input(tr("save_watchlist_as"), value=selected_watchlist if selected_watchlist != "Manuelle Eingabe" else tr("my_watchlist"))
    if st.button(tr("save_watchlist")):
        try:
            save_watchlist(watchlist_name, parse_symbols(watchlist_text))
            st.success(tr("watchlist_saved"))
        except ValueError as exc:
            st.error(str(exc))

    initial_capital = st.number_input(tr("initial_capital"), value=10_000.0, min_value=100.0, step=500.0, key="initial_capital_input")
    risk_per_trade = st.slider(tr("risk_per_trade"), min_value=0.0025, max_value=0.05, value=0.01, step=0.0025, key="risk_per_trade_input")
    st.caption(f"Maximales Risiko: {risk_per_trade * 100:.2f} % des gewählten Einsatzes")
    fee = st.slider(tr("fee_per_order"), min_value=0.0, max_value=0.01, value=0.001, step=0.0005, key="fee_input")
    st.caption(f"Gebühr je Order: {fee * 100:.2f} %")
    atr_stop = st.slider(tr("atr_stop"), min_value=0.5, max_value=5.0, value=2.0, step=0.25, key="atr_stop_input")
    atr_tp = st.slider(tr("atr_take_profit"), min_value=0.5, max_value=8.0, value=3.0, step=0.25, key="atr_tp_input")

alerts = recent_alerts()
with st.expander(tr("new_signals"), expanded=bool(alerts)):
    if alerts:
        st.dataframe(localized_dataframe(pd.DataFrame(alerts)), use_container_width=True)
    else:
        st.info(tr("no_buy_signals"))

history = recent_signal_history(50)
with st.expander(tr("signal_history"), expanded=False):
    if history:
        st.dataframe(localized_dataframe(pd.DataFrame(history)), use_container_width=True)
    else:
        st.info(tr("no_signals"))

symbols = parse_symbols(watchlist_text)
if not symbols:
    st.error(tr("no_symbols"))
    st.stop()

st.subheader("TradingView – Kerzenchart")
tradingview_selection = st.selectbox(
    "Symbol im TradingView-Fenster",
    symbols,
    key="tradingview_symbol_selection",
)
trade_amount = st.number_input(
    "Kapitaleinsatz pro Trade (€)",
    min_value=100.0,
    value=min(5_000.0, float(initial_capital)),
    step=500.0,
    help="Diese Summe wird für die Tages-Gewinnsimulation verwendet.",
)
paper_control_left, paper_control_right = st.columns([3, 1])
with paper_control_left:
    automatic_paper_trading = st.toggle(
        "Automatisches Paper-Trading aktivieren",
        value=True,
        help="Standardmäßig aktiv; kann jederzeit manuell pausiert werden. Es werden ausschließlich virtuelle Orders ausgeführt.",
    )
with paper_control_right:
    if st.button("Virtuelles Depot zurücksetzen", use_container_width=True):
        st.session_state["paper_account"] = PaperAccount.create(initial_capital)
        st.rerun()
st.caption("Interaktiver 15-Minuten-Chart. Symbol und Zeitintervall können direkt im Chart geändert werden.")
render_tradingview_chart(tradingview_selection)
render_daytrading_monitor(
    tradingview_selection, initial_capital, trade_amount, risk_per_trade,
    fee, atr_stop, atr_tp, automatic_paper_trading,
)
st.stop()

summary_rows = {}
data_cache = {}
trades_cache = {}
equity_cache = {}
metrics_cache = {}
progress = st.progress(0)

for idx, symbol in enumerate(symbols):
    try:
        raw = download_data(symbol, period=period, interval=interval)
        if len(raw) < 220 and interval == "1d":
            st.warning(tr("data_warning", symbol=symbol))

        df = generate_signals(add_indicators(raw))
        score = strategy_score(df)
        payload = signal_history_payload(symbol, score)
        save_signal_history(payload)
        create_alert_if_buy(payload)

        trades_df, equity_df = backtest(
            df,
            initial_capital=initial_capital,
            risk_per_trade=risk_per_trade,
            atr_stop_factor=atr_stop,
            atr_take_profit_factor=atr_tp,
            trading_fee=fee,
        )
        metrics = calculate_metrics(trades_df, equity_df, initial_capital)
        bh_metrics = buy_and_hold_metrics(df, initial_capital)
        strategy_return = metrics.get("Gesamtrendite %", 0.0)
        buy_hold_return = bh_metrics.get("BuyHold Rendite %", 0.0)

        summary_rows[symbol] = {
            "Symbol": symbol,
            "Signal": score["signal"],
            "Score %": score["score_pct"],
            "Kurs": round(score["close"], 2),
            "RSI": round(score["rsi"], 2),
            "ATR": round(score["atr"], 2),
            "Trades": metrics.get("Abgeschlossene Trades", 0),
            "Strategie Rendite %": round(strategy_return, 2),
            "BuyHold Rendite %": round(buy_hold_return, 2),
            "Differenz %": round(strategy_return - buy_hold_return, 2),
            "Strategie Drawdown %": round(metrics.get("Max. Drawdown %", 0.0), 2),
            "BuyHold Drawdown %": round(bh_metrics.get("BuyHold Max. Drawdown %", 0.0), 2),
            "Trefferquote %": round(metrics.get("Trefferquote %", 0.0), 2),
        }
        data_cache[symbol] = df
        trades_cache[symbol] = trades_df
        equity_cache[symbol] = equity_df
        metrics_cache[symbol] = {**metrics, **bh_metrics, "Differenz Rendite %": strategy_return - buy_hold_return}
    except Exception as exc:
        summary_rows[symbol] = {
            "Symbol": symbol,
            "Signal": f"Fehler: {exc}",
            "Score %": 0,
        }

    progress.progress((idx + 1) / len(symbols))

summary_df = pd.DataFrame(summary_rows.values()).sort_values("Score %", ascending=False)
valid_symbols = [symbol for symbol in summary_df["Symbol"].tolist() if symbol in data_cache]
if not valid_symbols:
    st.warning("Die Strategieauswertung wartet auf Kursdaten. TradingView und der Intraday-Monitor darüber können weiterhin verwendet werden.")
    st.stop()

current_user = str(st.session_state.get("auth_username", ""))
if st.session_state.get("login_defaults_applied_for") != current_user:
    if "AAPL" in valid_symbols:
        st.session_state["selected_detail_symbol"] = "AAPL"
    st.session_state["hyperopt2_objective_AAPL"] = "return"
    for default_criterion in ("trend", "rsi", "macd", "bollinger", "fibonacci", "volume", "stoch", "atr", "ichimoku", "risk_management"):
        st.session_state[f"hyperopt2_criterion_AAPL_{default_criterion}"] = True
    st.session_state["simulation_risk_management_AAPL"] = True
    st.session_state["login_defaults_applied_for"] = current_user

apple_index = valid_symbols.index("AAPL") if "AAPL" in valid_symbols else 0
selected_symbol = st.selectbox(
    tr("select_detail"), valid_symbols, index=apple_index, key="selected_detail_symbol"
)
df = data_cache[selected_symbol]
trades_df = trades_cache[selected_symbol]
equity_df = equity_cache[selected_symbol]
metrics = metrics_cache[selected_symbol]
score = strategy_score(df)

overview_tab, hyperopt2_tab, telemetry_tab, documentation_tab = st.tabs(
    [tr("overview"), "Hyperopt", tr("simulation"), tr("documentation")]
)

with overview_tab:
    st.caption(tr("tab_caption"))

with telemetry_tab:
    st.subheader(tr("simulation_title", symbol=selected_symbol))
    st.caption(tr("simulation_help"))

    available_dates = pd.to_datetime(df["Date"]).dt.date
    min_simulation_date = available_dates.min()
    max_simulation_date = available_dates.max()

    st.write(f"### {tr('time_window')}")
    date_col1, date_col2 = st.columns(2)
    simulation_start_date = date_col1.date_input(
        tr("start_date"),
        value=min_simulation_date,
        min_value=min_simulation_date,
        max_value=max_simulation_date,
        key=f"simulation_start_date_{selected_symbol}",
    )
    simulation_end_date = date_col2.date_input(
        tr("end_date"),
        value=max_simulation_date,
        min_value=min_simulation_date,
        max_value=max_simulation_date,
        key=f"simulation_end_date_{selected_symbol}",
    )

    st.write(f"### {tr('toggle_parameters')}")
    enabled_criteria = []
    toggle_columns = st.columns(5)
    simulation_short_labels = {
        "trend_filter": "Trend",
        "rsi_filter": "RSI",
        "macd_filter": "MACD",
        "bollinger_filter": "Bollinger",
        "fibonacci_filter": "Fibonacci",
        "volume_filter": localize_phrase("Volumen", language),
        "stochastic_filter": localize_phrase("Stochastik", language),
        "atr_filter": "ATR",
        "ichimoku_filter": "Ichimoku",
    }
    for criterion_index, criterion in enumerate(CRITERIA):
        with toggle_columns[criterion_index % 5]:
            is_enabled = st.checkbox(
                simulation_short_labels[criterion.criterion_id],
                value=True,
                key=f"simulation_criterion_{selected_symbol}_{criterion.criterion_id}",
            )
        if is_enabled:
            enabled_criteria.append(criterion.criterion_id)

    with toggle_columns[len(CRITERIA) % 5]:
        simulation_risk_management = st.checkbox(
            localize_phrase("Risikomanagement", language),
            value=True,
            key=f"simulation_risk_management_{selected_symbol}",
        )

    parameter_values = {
        "sma_trend_period": 50, "rsi_period": 14, "rsi_min": 40.0, "rsi_max": 65.0,
        "exit_rsi_max": 75.0, "macd_fast": 12, "macd_slow": 26, "macd_signal": 9,
        "bb_period": 20, "bb_std": 2.0, "fib_lookback": 120, "volume_period": 20,
        "volume_factor": 1.0, "stoch_period": 14, "stoch_signal": 3, "stoch_min": 20.0,
        "stoch_max": 80.0, "atr_period": 14, "atr_min_pct": 1.0, "atr_max_pct": 8.0,
        "ichimoku_tenkan": 9, "ichimoku_kijun": 26, "ichimoku_senkou_b": 52,
        "simulation_risk_pct": risk_per_trade * 100.0,
        "atr_stop_factor": atr_stop, "atr_take_profit_factor": atr_tp,
    }
    fields_by_criterion = {
        "trend_filter": [("sma_trend_period", 5, 200, 1)],
        "rsi_filter": [("rsi_period", 2, 50, 1), ("rsi_min", 0.0, 99.0, 1.0), ("rsi_max", 1.0, 100.0, 1.0), ("exit_rsi_max", 1.0, 100.0, 1.0)],
        "macd_filter": [("macd_fast", 2, 50, 1), ("macd_slow", 3, 100, 1), ("macd_signal", 2, 30, 1)],
        "bollinger_filter": [("bb_period", 5, 100, 1), ("bb_std", 0.5, 5.0, 0.1)],
        "fibonacci_filter": [("fib_lookback", 10, 500, 5)],
        "volume_filter": [("volume_period", 2, 100, 1), ("volume_factor", 0.1, 5.0, 0.1)],
        "stochastic_filter": [("stoch_period", 2, 50, 1), ("stoch_signal", 1, 20, 1), ("stoch_min", 0.0, 99.0, 1.0), ("stoch_max", 1.0, 100.0, 1.0)],
        "atr_filter": [("atr_period", 2, 100, 1), ("atr_min_pct", 0.0, 30.0, 0.1), ("atr_max_pct", 0.1, 50.0, 0.1)],
        "ichimoku_filter": [("ichimoku_tenkan", 2, 100, 1), ("ichimoku_kijun", 3, 200, 1), ("ichimoku_senkou_b", 4, 300, 1)],
        "risk_management": [("simulation_risk_pct", 0.25, 5.0, 0.25), ("atr_stop_factor", 0.5, 5.0, 0.25), ("atr_take_profit_factor", 0.5, 8.0, 0.25)],
    }
    with st.expander(tr("simulation_parameter_values"), expanded=True):
        st.caption(tr("simulation_parameter_help"))
        parameter_columns = st.columns(3)
        visible_fields = [field for criterion_id in enabled_criteria for field in fields_by_criterion[criterion_id]]
        if simulation_risk_management:
            visible_fields.extend(fields_by_criterion["risk_management"])
        for field_index, (field_name, minimum, maximum, step) in enumerate(visible_fields):
            with parameter_columns[field_index % 3]:
                parameter_values[field_name] = st.number_input(
                    parameter_label(field_name, language), min_value=minimum, max_value=maximum,
                    value=parameter_values[field_name], step=step,
                    key=f"simulation_value_{selected_symbol}_{field_name}",
                )

    simulation_indicator_params = IndicatorParameters(**{key: parameter_values[key] for key in IndicatorParameters.__dataclass_fields__})
    simulation_strategy_params = StrategyParameters(**{key: parameter_values[key] for key in StrategyParameters.__dataclass_fields__ if key in parameter_values})
    simulation_risk_per_trade = parameter_values["simulation_risk_pct"] / 100.0 if simulation_risk_management else risk_per_trade
    simulation_atr_stop = parameter_values["atr_stop_factor"] if simulation_risk_management else atr_stop
    simulation_atr_tp = parameter_values["atr_take_profit_factor"] if simulation_risk_management else atr_tp
    simulation_parameterized_df = generate_signals(add_indicators(df, simulation_indicator_params), simulation_strategy_params)

    if simulation_start_date > simulation_end_date:
        st.error(tr("invalid_dates"))
        simulation_source_df = simulation_parameterized_df.iloc[0:0].copy()
    else:
        simulation_source_df = simulation_parameterized_df[
            (pd.to_datetime(simulation_parameterized_df["Date"]).dt.date >= simulation_start_date)
            & (pd.to_datetime(simulation_parameterized_df["Date"]).dt.date <= simulation_end_date)
        ].copy()
        st.caption(tr("simulated_window", start=simulation_start_date, end=simulation_end_date, rows=len(simulation_source_df)))

    simulation_df = apply_enabled_criteria_signals(simulation_source_df, enabled_criteria)
    simulation_trades_df, simulation_equity_df = backtest(
        simulation_df,
        initial_capital=initial_capital,
        risk_per_trade=simulation_risk_per_trade,
        atr_stop_factor=simulation_atr_stop,
        atr_take_profit_factor=simulation_atr_tp,
        trading_fee=fee,
    )
    simulation_metrics = calculate_metrics(simulation_trades_df, simulation_equity_df, initial_capital)
    telemetry = build_criterion_telemetry(simulation_df, simulation_trades_df, enabled_criteria, simulation_strategy_params)
    summary_telemetry = telemetry["summary"]
    weekly_telemetry = telemetry["weekly"]
    monthly_telemetry = telemetry["monthly"]
    ranking_telemetry = telemetry["ranking"]
    events_telemetry = telemetry["events"]

    simulation_snapshot = {
        "symbol": selected_symbol,
        "period": period,
        "interval": interval,
        "initial_capital": initial_capital,
        "fee": fee,
        "sidebar_risk_per_trade": risk_per_trade,
        "sidebar_atr_stop": atr_stop,
        "sidebar_atr_tp": atr_tp,
        "start_date": simulation_start_date,
        "end_date": simulation_end_date,
        "enabled_criteria": list(enabled_criteria),
        "risk_management": simulation_risk_management,
        "parameter_values": dict(parameter_values),
        "metrics": simulation_metrics,
        "trades": simulation_trades_df,
        "equity": simulation_equity_df,
        "summary": summary_telemetry,
        "ranking": ranking_telemetry,
    }
    st.write(f"### {tr('saved_results')}")
    saved_simulation_results = list_analysis_results(current_user, "simulation", selected_symbol)
    simulation_save_name = st.text_input(
        tr("result_name"),
        value=f"{selected_symbol} Simulation",
        key=f"simulation_result_name_{selected_symbol}",
    )
    simulation_save_col, simulation_load_col = st.columns(2)
    with simulation_save_col:
        simulation_save_button_col, simulation_load_button_col, _ = st.columns([1, 1.15, 3.5])
    with simulation_save_button_col:
        if st.button(tr("save_result"), key=f"save_simulation_result_{selected_symbol}"):
            save_analysis_result(
                current_user,
                "simulation",
                simulation_save_name,
                selected_symbol,
                simulation_snapshot,
            )
            st.success(tr("result_saved"))
    with simulation_load_col:
        if saved_simulation_results:
            selected_simulation_result_id = st.selectbox(
                tr("saved_results"),
                [item["id"] for item in saved_simulation_results],
                format_func=lambda result_id: next(item["name"] for item in saved_simulation_results if item["id"] == result_id),
                key=f"saved_simulation_result_{selected_symbol}",
            )

            def load_saved_simulation_result() -> None:
                loaded = load_analysis_result(current_user, selected_simulation_result_id, "simulation")
                st.session_state["period_input"] = loaded["period"]
                st.session_state["interval_input"] = loaded["interval"]
                st.session_state["initial_capital_input"] = float(loaded["initial_capital"])
                st.session_state["fee_input"] = float(loaded["fee"])
                st.session_state["risk_per_trade_input"] = float(loaded["sidebar_risk_per_trade"])
                st.session_state["atr_stop_input"] = float(loaded["sidebar_atr_stop"])
                st.session_state["atr_tp_input"] = float(loaded["sidebar_atr_tp"])
                st.session_state[f"simulation_start_date_{selected_symbol}"] = loaded["start_date"]
                st.session_state[f"simulation_end_date_{selected_symbol}"] = loaded["end_date"]
                enabled = set(loaded["enabled_criteria"])
                for criterion in CRITERIA:
                    st.session_state[f"simulation_criterion_{selected_symbol}_{criterion.criterion_id}"] = criterion.criterion_id in enabled
                st.session_state[f"simulation_risk_management_{selected_symbol}"] = bool(loaded["risk_management"])
                for parameter_name, parameter_value in loaded["parameter_values"].items():
                    st.session_state[f"simulation_value_{selected_symbol}_{parameter_name}"] = parameter_value
                st.session_state["loaded_simulation_result"] = True

        else:
            st.info(tr("no_saved_results"))

    if saved_simulation_results:
        with simulation_load_button_col:
            st.button(
                tr("load_result"),
                key=f"load_simulation_result_{selected_symbol}",
                on_click=load_saved_simulation_result,
            )
    if st.session_state.pop("loaded_simulation_result", False):
        st.success(tr("result_loaded"))

    if summary_telemetry.empty:
        if not enabled_criteria:
            st.info(tr("enable_criterion"))
        elif len(simulation_source_df) < 2:
            st.info(tr("too_few_prices"))
        else:
            st.info(tr("no_telemetry"))
    else:
        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
        metric_col1.metric(tr("active_criteria"), summary_telemetry["Kriterium"].nunique() + int(simulation_risk_management))
        metric_col2.metric(tr("evaluations"), int(summary_telemetry["evaluation_count"].sum()))
        metric_col3.metric(tr("trades"), simulation_metrics.get("Abgeschlossene Trades", 0))
        metric_col4.metric(tr("return"), f"{simulation_metrics.get('Gesamtrendite %', 0.0):.2f}%")

        st.write(f"### {tr('simulation_metrics')}")
        st.dataframe(localized_dataframe(format_metrics(simulation_metrics)), use_container_width=True)

        display_summary = summary_telemetry.rename(
            columns={
                "evaluation_count": "Pruefungen",
                "passed_count": "Erfuellt",
                "trigger_count": "Ausloeser",
                "block_count": "Blockiert",
                "support_count": "Unterstuetzt",
                "decisive_count": "Entscheidend",
                "estimated_profit_contribution": "Profitbeitrag geschaetzt",
                "estimated_loss_avoidance": "Verlustvermeidung geschaetzt",
                "estimated_missed_profit_pct": "Verpasster Gewinn % geschaetzt",
                "confidence_score": "Konfidenz",
            }
        )
        st.write(f"### {tr('single_run')}")
        st.dataframe(
            localized_dataframe(display_summary[
                [
                    "Kriterium",
                    "Gruppe",
                    "Pruefungen",
                    "Erfuellt",
                    "Ausloeser",
                    "Blockiert",
                    "Unterstuetzt",
                    "Entscheidend",
                    "Profitbeitrag geschaetzt",
                    "Verlustvermeidung geschaetzt",
                    "Verpasster Gewinn % geschaetzt",
                    "Konfidenz",
                    "Bewertung",
                ]
            ]),
            use_container_width=True,
        )

        st.write(f"### {tr('rankings')}")
        ranking_view = ranking_telemetry.rename(
            columns={
                "criterion_relevance_score": "Relevanzscore",
                "decision_score": "Entscheidungseinfluss",
                "profit_score": "Profit-Score",
                "risk_score": "Risiko-Score",
                "stability_score": "Stabilitaet",
            }
        )
        st.dataframe(
            localized_dataframe(ranking_view[
                [
                    "Kriterium",
                    "Relevanzscore",
                    "Entscheidungseinfluss",
                    "Profit-Score",
                    "Risiko-Score",
                    "Stabilitaet",
                    "Bewertung",
                ]
            ]),
            use_container_width=True,
        )

        st.write(f"### {tr('aggregates')}")
        sub_tab_week, sub_tab_month, sub_tab_events = st.tabs([tr("weeks"), tr("months"), tr("signal_events")])
        with sub_tab_week:
            st.dataframe(localized_dataframe(weekly_telemetry), use_container_width=True)
        with sub_tab_month:
            st.dataframe(localized_dataframe(monthly_telemetry), use_container_width=True)
        with sub_tab_events:
            event_view = events_telemetry[events_telemetry["role"] != "none"].copy()
            st.dataframe(localized_dataframe(event_view.tail(500)), use_container_width=True)

        st.write(f"### {tr('mc_title')}")
        st.caption(tr("mc_help"))
        mc_col1, mc_col2 = st.columns(2)
        monte_carlo_runs = mc_col1.slider(
            tr("mc_paths"),
            min_value=50,
            max_value=500,
            value=200,
            step=50,
            key=f"mc_runs_{selected_symbol}",
        )
        monte_carlo_seed = mc_col2.number_input(
            tr("random_seed"),
            min_value=1,
            max_value=999_999,
            value=42,
            step=1,
            key=f"mc_seed_{selected_symbol}",
        )
        run_monte_carlo_button = st.button(
            tr("start_mc"),
            type="primary",
            key=f"run_mc_{selected_symbol}",
        )

        if run_monte_carlo_button:
            with st.spinner(tr("mc_spinner", runs=monte_carlo_runs, symbol=selected_symbol)):
                st.session_state["monte_carlo_result"] = {
                    "symbol": selected_symbol,
                    "criteria": tuple(enabled_criteria),
                    "runs": monte_carlo_runs,
                    "seed": int(monte_carlo_seed),
                    "data": run_monte_carlo_robustness(
                        history_df=simulation_source_df,
                        enabled_criteria=enabled_criteria,
                        initial_capital=initial_capital,
                        risk_per_trade=risk_per_trade,
                        atr_stop_factor=atr_stop,
                        atr_take_profit_factor=atr_tp,
                        trading_fee=fee,
                        config=MonteCarloConfig(simulations=monte_carlo_runs, future_days=252, seed=int(monte_carlo_seed)),
                    ),
                }

        monte_carlo_result = st.session_state.get("monte_carlo_result")
        if monte_carlo_result and monte_carlo_result["symbol"] == selected_symbol:
            mc_data = monte_carlo_result["data"]
            mc_summary = mc_data["summary"]
            mc_results = mc_data["results"]
            mc_paths = mc_data["paths"]
            if mc_summary.empty:
                st.info(tr("mc_too_short"))
            else:
                score_value = float(mc_summary["Robustheits-Score %"].iloc[0])
                score_color = "#22c55e" if score_value >= 67 else "#f59e0b" if score_value >= 34 else "#ef4444"
                st.markdown(
                    f"<h4>{tr('mc_score')}: <span style='color:{score_color}'>{score_value:.1f}%</span></h4>",
                    unsafe_allow_html=True,
                )
                st.dataframe(localized_dataframe(mc_summary), use_container_width=True)
                st.plotly_chart(localized_figure(make_monte_carlo_paths_chart(mc_paths, selected_symbol)), use_container_width=True)
                st.write(f"### {tr('mc_individual')}")
                st.dataframe(localized_dataframe(mc_results.sort_values("Strategierendite %", ascending=False)), use_container_width=True)
                st.download_button(
                    tr("mc_download"),
                    localized_dataframe(mc_results).to_csv(index=False).encode("utf-8-sig"),
                    f"{selected_symbol}_monte_carlo_robustheit.csv",
                    "text/csv",
                )
        else:
            st.info(tr("mc_not_started"))

        st.download_button(
            tr("criteria_download"),
            localized_dataframe(summary_telemetry).to_csv(index=False).encode("utf-8-sig"),
            f"{selected_symbol}_kriterien_telemetrie.csv",
            "text/csv",
        )
        st.download_button(
            tr("events_download"),
            localized_dataframe(events_telemetry).to_csv(index=False).encode("utf-8-sig"),
            f"{selected_symbol}_kriterien_ereignisse.csv",
            "text/csv",
        )

with overview_tab:
    st.subheader(tr("strategy_chart", symbol=selected_symbol))
    st.plotly_chart(localized_figure(make_chart(df, selected_symbol)), use_container_width=True)
    
    st.subheader(tr("strategy_parameters"))
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(tr("signal"), localize_phrase(score["signal"], language))
    col2.metric(tr("strategy_score"), f"{score['score']}/{score['max_score']}")
    col3.metric("RSI", f"{score['rsi']:.2f}")
    col4.metric("ATR", f"{score['atr']:.2f}")
    
    check_df = pd.DataFrame([{tr("criterion"): localize_phrase(key, language), tr("fulfilled"): tr("yes") if value else tr("no")} for key, value in score["checks"].items()])
    st.write(f"### {tr('criteria_check')}")
    st.dataframe(check_df, use_container_width=True)
    
    st.write(f"### {tr('watchlist_ranking')}")
    st.dataframe(localized_dataframe(summary_df), use_container_width=True)
    
    st.write(f"### {tr('backtest_metrics')}")
    st.dataframe(localized_dataframe(format_metrics(metrics)), use_container_width=True)
    
if False:  # Alter Optimierungsbereich deaktiviert; der neue Hyperopt-Bereich wird weiter unten gerendert.
    if enable_hyperopt:
        st.write("### Hyperopt")
        st.caption(tr("hyperopt_help"))
        criteria_labels = {
            "trend": "SMA Trend positiv",
            "rsi": "RSI im Zielbereich",
            "macd": "MACD bullisch",
            "bollinger": "Bollinger Momentum positiv",
            "fibonacci": "Fibonacci Unterstuetzung haelt",
            "volume": "Volumen bestaetigt",
            "stoch": "Stochastik positiv",
            "atr": "ATR Volatilitaet handelbar",
            "ichimoku": "Ichimoku bullisch",
            "risk_management": tr("risk_management_opt"),
        }
        criteria_labels = {key: localize_phrase(value, language) for key, value in criteria_labels.items()}
        st.write(f"### {tr('hyperopt_criteria')}")
        st.caption(tr("hyperopt_criteria_help"))
        criteria_defaults = {
            "trend": True,
            "rsi": True,
            "macd": True,
            "bollinger": True,
            "fibonacci": False,
            "volume": True,
            "stoch": False,
            "atr": False,
            "ichimoku": False,
            "risk_management": False,
        }
        hyperopt_criteria = {}
        criteria_columns = st.columns(3)
        for criterion_index, (criterion_key, criterion_label) in enumerate(criteria_labels.items()):
            with criteria_columns[criterion_index % 3]:
                hyperopt_criteria[criterion_key] = st.checkbox(
                    criterion_label,
                    value=criteria_defaults[criterion_key],
                    key=f"hyperopt_criterion_{selected_symbol}_{criterion_key}",
                )
        if not any(hyperopt_criteria.values()):
            st.warning(tr("criterion_required"))

        st.write(f"### {tr('analysis_window')}")
        hyperopt_available_dates = pd.to_datetime(df["Date"]).dt.date
        hyperopt_min_date = hyperopt_available_dates.min()
        hyperopt_max_date = hyperopt_available_dates.max()
        hyperopt_date_col1, hyperopt_date_col2 = st.columns(2)
        hyperopt_start_date = hyperopt_date_col1.date_input(
            tr("hyperopt_start"),
            value=hyperopt_min_date,
            min_value=hyperopt_min_date,
            max_value=hyperopt_max_date,
            key=f"hyperopt_start_date_{selected_symbol}",
        )
        hyperopt_end_date = hyperopt_date_col2.date_input(
            tr("hyperopt_end"),
            value=hyperopt_max_date,
            min_value=hyperopt_min_date,
            max_value=hyperopt_max_date,
            key=f"hyperopt_end_date_{selected_symbol}",
        )
        if hyperopt_start_date > hyperopt_end_date:
            st.error(tr("hyperopt_dates_invalid"))
            hyperopt_source_df = df.iloc[0:0].copy()
        else:
            hyperopt_source_df = df[
                (pd.to_datetime(df["Date"]).dt.date >= hyperopt_start_date)
                & (pd.to_datetime(df["Date"]).dt.date <= hyperopt_end_date)
            ].copy()
            st.caption(tr("hyperopt_window", start=hyperopt_start_date, end=hyperopt_end_date, rows=len(hyperopt_source_df)))

        run_hyperopt_button = st.button(tr("start_hyperopt"), type="primary")
    
        if run_hyperopt_button:
            if len(hyperopt_source_df) < 220:
                st.warning(tr("hyperopt_short"))
            else:
                with st.spinner(tr("hyperopt_spinner", symbol=selected_symbol, trials=hyperopt_trials)):
                    st.session_state["hyperopt_result"] = {
                        "symbol": selected_symbol,
                        "start_date": hyperopt_start_date,
                        "end_date": hyperopt_end_date,
                        "data": run_hyperopt(
                            hyperopt_source_df,
                            initial_capital=initial_capital,
                            trading_fee=fee,
                            risk_per_trade=risk_per_trade,
                            atr_stop_factor=atr_stop,
                            atr_take_profit_factor=atr_tp,
                            max_trials=hyperopt_trials,
                            min_trades=hyperopt_min_trades,
                            enabled_criteria=hyperopt_criteria,
                        ),
                    }
    
        hyperopt_result = st.session_state.get("hyperopt_result")
        if (
            hyperopt_result
            and hyperopt_result["symbol"] == selected_symbol
            and hyperopt_result.get("start_date") == hyperopt_start_date
            and hyperopt_result.get("end_date") == hyperopt_end_date
        ):
            hyperopt_df = hyperopt_result["data"]
            best_params = best_hyperopt_parameters(hyperopt_df)
    
            if best_params is None:
                st.info(tr("no_hyperopt"))
            else:
                opt_indicator_df = add_indicators(hyperopt_source_df, best_params.indicator_parameters())
                opt_signal_df = generate_signals(opt_indicator_df, best_params.strategy_parameters(hyperopt_criteria))
                st.write(f"### {tr('convergence')}")
                st.plotly_chart(localized_figure(make_hyperopt_convergence_chart(hyperopt_df, selected_symbol)), use_container_width=True)
                st.write(f"### {tr('best_parameters')}")
                parameter_df = localized_dataframe(pd.DataFrame(hyperopt_parameter_rows(best_params, hyperopt_criteria, hyperopt_df)))
                impact_column = localize_phrase("Einfluss %", language)
                value_column_label = localize_phrase("Hyperopt-Wert", language)
                styled_parameter_df = parameter_df.style.apply(
                    lambda row: [influence_color(float(row.get(impact_column, 0.0))) if column in {impact_column, localize_phrase("Wichtigkeit", language)} else "" for column in row.index],
                    axis=1,
                ).format(
                    {
                        value_column_label: lambda value: f"{value:.4f}".rstrip("0").rstrip(".")
                        if isinstance(value, float)
                        else value,
                        impact_column: "{:.0f}",
                    }
                )
                st.caption(tr("importance_help"))
                st.dataframe(styled_parameter_df, use_container_width=True)
                st.write(f"### {tr('candlestick_chart', symbol=selected_symbol)}")
                st.plotly_chart(localized_figure(make_candlestick_chart(hyperopt_source_df, selected_symbol)), use_container_width=True)
        else:
            st.info(tr("hyperopt_not_started"))

with hyperopt2_tab:
    st.subheader("Hyperopt")
    st.caption(tr("h2_help"))
    st.info(tr("h2_selection_help"))
    objective = st.selectbox(
        tr("objective"),
        list(OBJECTIVES),
        format_func=lambda value: localize_phrase(OBJECTIVES[value], language),
        index=list(OBJECTIVES).index("return"),
        key=f"hyperopt2_objective_{selected_symbol}",
    )
    h2_criteria_defaults = {
        "trend": True,
        "rsi": True,
        "macd": True,
        "bollinger": True,
        "fibonacci": True,
        "volume": True,
        "stoch": True,
        "atr": True,
        "ichimoku": True,
        "risk_management": True,
    }
    h2_labels = {
        "trend": "Trend", "rsi": "RSI", "macd": "MACD", "bollinger": "Bollinger",
        "fibonacci": "Fibonacci", "volume": localize_phrase("Volumen", language), "stoch": localize_phrase("Stochastik", language),
        "atr": "ATR", "ichimoku": "Ichimoku", "risk_management": localize_phrase("Risikomanagement", language),
    }
    h2_criteria = {}
    h2_columns = st.columns(5)
    for h2_index, (h2_key, h2_label) in enumerate(h2_labels.items()):
        with h2_columns[h2_index % 5]:
            h2_criteria[h2_key] = st.checkbox(
                h2_label,
                value=h2_criteria_defaults[h2_key],
                key=f"hyperopt2_criterion_{selected_symbol}_{h2_key}",
            )

    if st.button(tr("run"), type="primary", key=f"run_hyperopt2_{selected_symbol}"):
        if len(df) < 220:
            st.warning(tr("h2_short"))
        else:
            with st.spinner(tr("h2_spinner", symbol=selected_symbol)):
                st.session_state["hyperopt2_result"] = {
                    "symbol": selected_symbol,
                    "objective": objective,
                    "criteria": h2_criteria.copy(),
                    "data": run_hyperopt2(
                        df,
                        initial_capital=initial_capital,
                        trading_fee=fee,
                        risk_per_trade=risk_per_trade,
                        atr_stop_factor=atr_stop,
                        atr_take_profit_factor=atr_tp,
                        max_trials=hyperopt_trials,
                        min_trades=hyperopt_min_trades,
                        objective=objective,
                        enabled_criteria=h2_criteria,
                    ),
                }

    st.write(f"### {tr('saved_results')}")
    saved_hyperopt_results = list_analysis_results(current_user, "hyperopt", selected_symbol)
    hyperopt_save_name = st.text_input(
        tr("result_name"),
        value=f"{selected_symbol} Hyperopt",
        key=f"hyperopt_result_name_{selected_symbol}",
    )
    hyperopt_save_col, hyperopt_load_col = st.columns(2)
    with hyperopt_save_col:
        hyperopt_save_button_col, hyperopt_load_button_col, _ = st.columns([1, 1.15, 3.5])
    with hyperopt_load_col:
        if saved_hyperopt_results:
            selected_hyperopt_result_id = st.selectbox(
                tr("saved_results"),
                [item["id"] for item in saved_hyperopt_results],
                format_func=lambda result_id: next(item["name"] for item in saved_hyperopt_results if item["id"] == result_id),
                key=f"saved_hyperopt_result_{selected_symbol}",
            )

            def load_saved_hyperopt_result() -> None:
                loaded_state = load_analysis_result(current_user, selected_hyperopt_result_id, "hyperopt")
                if isinstance(loaded_state.get("data"), dict):
                    loaded_state["data"] = hyperopt2_result_from_payload(loaded_state["data"])
                st.session_state[f"hyperopt2_objective_{selected_symbol}"] = loaded_state["objective"]
                st.session_state["hyperopt2_result"] = loaded_state
                st.session_state["loaded_hyperopt_result"] = True

        else:
            st.info(tr("no_saved_results"))

    h2_state = st.session_state.get("hyperopt2_result")
    with hyperopt_save_button_col:
        if st.button(
            tr("save_result"),
            key=f"save_hyperopt_result_{selected_symbol}",
            disabled=not bool(h2_state and h2_state.get("symbol") == selected_symbol),
        ):
            portable_hyperopt_state = dict(h2_state)
            portable_hyperopt_state["data"] = hyperopt2_result_to_payload(h2_state["data"])
            save_analysis_result(
                current_user,
                "hyperopt",
                hyperopt_save_name,
                selected_symbol,
                portable_hyperopt_state,
            )
            st.success(tr("result_saved"))
    if saved_hyperopt_results:
        with hyperopt_load_button_col:
            st.button(
                tr("load_result"),
                key=f"load_hyperopt_result_{selected_symbol}",
                on_click=load_saved_hyperopt_result,
            )
    if st.session_state.pop("loaded_hyperopt_result", False):
        st.success(tr("result_loaded"))

    if h2_state and h2_state["symbol"] == selected_symbol and h2_state["objective"] == objective:
        h2_result = h2_state["data"]
        h2_best = best_hyperopt2_parameters(h2_result)
        h2_recommended = recommended_criteria(h2_result)
        metric_a, metric_b, metric_c, metric_d = st.columns(4)
        best_row = h2_result.trials.iloc[0]
        metric_a.metric(tr("yield"), f"{best_row['Gesamtrendite %']:.2f} %")
        metric_b.metric(tr("drawdown"), f"{best_row['Max. Drawdown %']:.2f} %")
        metric_c.metric(tr("trades"), int(best_row["Abgeschlossene Trades"]))
        metric_d.metric(tr("stability"), f"{h2_result.stability_index:.1f}/100")

        st.write(f"### {tr('convergence')}")
        st.plotly_chart(
            localized_figure(
                make_hyperopt_convergence_chart(
                    h2_result.trials,
                    selected_symbol,
                    optimizer_name="Hyperopt",
                )
            ),
            use_container_width=True,
        )

        st.write(f"### {tr('h2_recommendation')}")
        if h2_best is not None:
            criterion_names = {
                "trend": "Trend", "rsi": "RSI", "macd": "MACD", "bollinger": "Bollinger",
                "fibonacci": "Fibonacci", "volume": "Volumen", "stoch": "Stochastik",
                "atr": "ATR", "ichimoku": "Ichimoku",
            }
            active_h2_criteria = [key for key, active in h2_recommended.items() if active]
            criterion_rows = [
                {
                    tr("criterion"): localize_phrase(criterion_names[key], language),
                    tr("h2_use"): tr("yes") if h2_recommended.get(key, False) else tr("no"),
                }
                for key in criterion_names if key in h2_recommended
            ]
            st.write(f"#### {tr('h2_recommended_criteria')}")
            st.dataframe(pd.DataFrame(criterion_rows), use_container_width=True, hide_index=True)

            parameter_groups = {
                "trend": ["sma_trend_period"],
                "rsi": ["rsi_period", "rsi_min", "rsi_max", "exit_rsi_max"],
                "macd": ["macd_fast", "macd_slow", "macd_signal"],
                "bollinger": ["bb_period", "bb_std"],
                "fibonacci": ["fib_lookback"],
                "volume": ["volume_period", "volume_factor"],
                "stoch": ["stoch_period", "stoch_signal", "stoch_min", "stoch_max"],
                "atr": ["atr_period", "atr_min_pct", "atr_max_pct"],
                "ichimoku": ["ichimoku_tenkan", "ichimoku_kijun", "ichimoku_senkou_b"],
            }
            parameter_rows = []
            for criterion_key in active_h2_criteria:
                for parameter_name in parameter_groups[criterion_key]:
                    parameter_rows.append({
                        tr("criterion"): localize_phrase(criterion_names[criterion_key], language),
                        tr("h2_parameter"): parameter_label(parameter_name, language),
                        tr("h2_value"): getattr(h2_best, parameter_name),
                    })
            if h2_state.get("criteria", {}).get("risk_management", False):
                for parameter_name in ("risk_per_trade", "atr_stop_factor", "atr_take_profit_factor"):
                    parameter_rows.append({
                        tr("criterion"): localize_phrase("Risikomanagement", language),
                        tr("h2_parameter"): parameter_label(parameter_name, language),
                        tr("h2_value"): getattr(h2_best, parameter_name),
                    })
            st.write(f"#### {tr('h2_recommended_values')}")
            st.dataframe(pd.DataFrame(parameter_rows), use_container_width=True, hide_index=True)

            criterion_widget_ids = {
                "trend": "trend_filter", "rsi": "rsi_filter", "macd": "macd_filter",
                "bollinger": "bollinger_filter", "fibonacci": "fibonacci_filter",
                "volume": "volume_filter", "stoch": "stochastic_filter", "atr": "atr_filter",
                "ichimoku": "ichimoku_filter",
            }

            def apply_h2_to_simulation() -> None:
                for criterion_key, criterion_id in criterion_widget_ids.items():
                    st.session_state[f"simulation_criterion_{selected_symbol}_{criterion_id}"] = bool(
                        h2_recommended.get(criterion_key, False)
                    )
                risk_is_enabled = bool(h2_state.get("criteria", {}).get("risk_management", False))
                st.session_state[f"simulation_risk_management_{selected_symbol}"] = risk_is_enabled
                for parameter_name in hyperopt_module.HyperoptParameters.__dataclass_fields__:
                    if parameter_name in IndicatorParameters.__dataclass_fields__ or parameter_name in StrategyParameters.__dataclass_fields__:
                        st.session_state[f"simulation_value_{selected_symbol}_{parameter_name}"] = getattr(h2_best, parameter_name)
                if h2_state.get("criteria", {}).get("risk_management", False):
                    st.session_state[f"simulation_value_{selected_symbol}_simulation_risk_pct"] = float(h2_best.risk_per_trade) * 100.0
                    st.session_state[f"simulation_value_{selected_symbol}_atr_stop_factor"] = float(h2_best.atr_stop_factor)
                    st.session_state[f"simulation_value_{selected_symbol}_atr_take_profit_factor"] = float(h2_best.atr_take_profit_factor)
                    st.session_state["risk_per_trade_input"] = float(h2_best.risk_per_trade)
                    st.session_state["atr_stop_input"] = float(h2_best.atr_stop_factor)
                    st.session_state["atr_tp_input"] = float(h2_best.atr_take_profit_factor)
                st.session_state["h2_applied_to_simulation"] = True

            st.button(
                tr("h2_apply_simulation"),
                type="primary",
                key=f"apply_h2_simulation_{selected_symbol}",
                on_click=apply_h2_to_simulation,
            )
            if st.session_state.pop("h2_applied_to_simulation", False):
                st.success(tr("h2_applied_simulation"))

        with st.expander(tr("h2_details")):
            st.dataframe(localized_dataframe(h2_result.benchmarks).style.format({localize_phrase("Rendite %", language): "{:.2f}", localize_phrase("Endkapital", language): "{:.2f}"}), use_container_width=True)

        left_chart, right_chart = st.columns(2)
        with left_chart:
            st.write(f"### {tr('importance')}")
            importance_fig = go.Figure(go.Bar(
                x=h2_result.importance["Importance %"],
                y=h2_result.importance["Parameter"].map(lambda value: parameter_label(value, language)),
                orientation="h",
            ))
            importance_fig.update_layout(height=480, yaxis={"autorange": "reversed"}, xaxis_title="Importance %")
            st.plotly_chart(localized_figure(importance_fig), use_container_width=True)
        with right_chart:
            st.write(f"### {tr('heatmap')}")
            heatmap_fig = go.Figure()
            if not h2_result.heatmap.empty:
                heatmap_fig.add_trace(go.Heatmap(
                    z=h2_result.heatmap.values,
                    x=[str(value) for value in h2_result.heatmap.columns],
                    y=[str(value) for value in h2_result.heatmap.index],
                    colorscale="RdYlGn",
                    colorbar={"title": "Objective"},
                ))
                heatmap_fig.update_layout(
                    height=480,
                    xaxis_title=parameter_label(str(h2_result.heatmap.columns.name), language),
                    yaxis_title=parameter_label(str(h2_result.heatmap.index.name), language),
                )
            st.plotly_chart(localized_figure(heatmap_fig), use_container_width=True)

        st.write(f"### {tr('sensitivity')}")
        sensitivity_fig = go.Figure()
        for parameter, parameter_df in h2_result.sensitivity.groupby("Parameter"):
            sensitivity_fig.add_trace(go.Scatter(
                x=parameter_df["Wert"],
                y=parameter_df["Objective Mittel"],
                mode="lines+markers",
                name=parameter_label(parameter, language),
            ))
        sensitivity_fig.update_layout(height=430, xaxis_title=tr("parameter_value"), yaxis_title=tr("objective_mean"))
        st.plotly_chart(localized_figure(sensitivity_fig), use_container_width=True)
        st.write(f"### {tr('evaluation')}")
        st.info(localize_phrase(h2_result.evaluation, language))
        st.download_button(
            tr("h2_download"),
            localized_dataframe(h2_result.trials).to_csv(index=False).encode("utf-8-sig"),
            f"{selected_symbol}_hyperopt.csv",
            "text/csv",
        )
    else:
        st.info(tr("not_started_h2"))

with documentation_tab:
    st.markdown(DOCUMENTATION[language])

with overview_tab:
    if not equity_df.empty:
        st.plotly_chart(localized_figure(make_equity_chart(equity_df, selected_symbol)), use_container_width=True)
    
    st.write(f"### {tr('trades')}")
    if trades_df.empty:
        st.info(tr("no_trades"))
    else:
        st.dataframe(localized_dataframe(trades_df), use_container_width=True)
    
    st.download_button(tr("ranking_download"), localized_dataframe(summary_df).to_csv(index=False).encode("utf-8-sig"), "watchlist_ranking.csv", "text/csv")
    if not trades_df.empty:
        st.download_button(
            tr("trades_download"),
            localized_dataframe(trades_df).to_csv(index=False).encode("utf-8-sig"),
            f"{selected_symbol}_trades.csv",
            "text/csv",
        )
