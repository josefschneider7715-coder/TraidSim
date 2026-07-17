from __future__ import annotations

import hashlib
import hmac
import importlib
import base64
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.backtest import backtest, buy_and_hold_metrics, calculate_metrics
from src.data_provider import download_data
from src.indicators import add_indicators
from src.scoring import signal_history_payload, strategy_score
from src.storage import create_alert_if_buy, list_watchlists, recent_alerts, recent_signal_history, save_signal_history, save_watchlist
from src.strategy import generate_signals
from src import charts as charts_module
from src import hyperopt as hyperopt_module
from src import telemetry as telemetry_module


charts_module = importlib.reload(charts_module)
hyperopt_module = importlib.reload(hyperopt_module)
telemetry_module = importlib.reload(telemetry_module)
make_candlestick_chart = charts_module.make_candlestick_chart
make_chart = charts_module.make_chart
make_equity_chart = charts_module.make_equity_chart
best_hyperopt_parameters = hyperopt_module.best_hyperopt_parameters
run_hyperopt = hyperopt_module.run_hyperopt
CRITERIA = telemetry_module.CRITERIA
apply_enabled_criteria_signals = telemetry_module.apply_enabled_criteria_signals
build_criterion_telemetry = telemetry_module.build_criterion_telemetry


APP_DIR = Path(__file__).parent
LOGO_PATH = APP_DIR / "assets" / "traidsim_logo.png"


st.set_page_config(page_title="TraidSim", page_icon="chart_with_upwards_trend", layout="wide")


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
    auth_config = get_auth_config()
    users = dict(auth_config.get("users", {}))
    if not users and auth_config.get("username") and auth_config.get("password_sha256"):
        users = {str(auth_config["username"]): str(auth_config["password_sha256"])}

    if not users:
        st.error("Login ist nicht eingerichtet. Bitte .streamlit/secrets.toml mit Benutzer und Passwort-Hash anlegen.")
        st.stop()

    if st.session_state.get("authenticated"):
        with st.sidebar:
            st.caption(f"Angemeldet als {st.session_state.get('auth_username', '')}")
            if st.button("Abmelden"):
                st.session_state.pop("authenticated", None)
                st.session_state.pop("auth_username", None)
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
        st.caption("Bitte anmelden, um fortzufahren.")
        with st.form("login_form"):
            username = st.text_input("Benutzername")
            password = st.text_input("Passwort", type="password")
            submitted = st.form_submit_button("Anmelden", type="primary")
        st.caption("Passwort vergessen? Bitte Administrator kontaktieren.")

    if submitted:
        expected_password_hash = str(users.get(username, ""))
        if expected_password_hash and password_matches(password, expected_password_hash):
            st.session_state["authenticated"] = True
            st.session_state["auth_username"] = username
            st.rerun()
        st.error("Benutzername oder Passwort ist falsch.")

    st.stop()


require_login()

DISCLAIMER = """
Dies ist ein technisches Analyse- und Backtesting-Tool. Es handelt sich nicht um Anlageberatung.
Die Signale sind regelbasierte technische Auswertungen und keine persoenliche Kauf- oder Verkaufsempfehlung.
"""

DEFAULT_WATCHLIST = "AAPL,AMZN,NVDA,MSFT,GOOGL,BTC-USD,ETH-USD,SOL-USD,1211.HK"


def parse_symbols(raw_symbols: str) -> list[str]:
    return [symbol.strip().upper() for symbol in raw_symbols.split(",") if symbol.strip()]


def format_metrics(metrics: dict) -> pd.DataFrame:
    return pd.DataFrame([{key: round(value, 2) if isinstance(value, float) else value for key, value in metrics.items()}])


def format_hyperopt_value(value):
    if isinstance(value, float):
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
        (None, "Risikomanagement", "Risiko je Trade", "risk_per_trade"),
        (None, "Risikomanagement", "ATR Stop-Faktor", "atr_stop_factor"),
        (None, "Risikomanagement", "ATR Take-Profit-Faktor", "atr_take_profit_factor"),
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


def make_hyperopt_convergence_chart(results_df: pd.DataFrame, symbol: str):
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
        title=f"{symbol} - Hyperopt Konvergenz zur besten Loesung",
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


def make_criterion_heatmap(period_df: pd.DataFrame, value_column: str, title: str):
    if period_df.empty:
        return go.Figure()

    pivot = period_df.pivot_table(index="Kriterium", columns="Periode", values=value_column, aggfunc="sum", fill_value=0)
    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=pivot.columns,
            y=pivot.index,
            colorscale=[
                [0.0, "#e5e7eb"],
                [0.25, "#60a5fa"],
                [0.5, "#facc15"],
                [0.75, "#22c55e"],
                [1.0, "#7c3aed"],
            ],
            colorbar={"title": value_column.replace("_", " ")},
            hovertemplate="Kriterium: %{y}<br>Periode: %{x}<br>Wert: %{z}<extra></extra>",
        )
    )
    fig.update_layout(title=title, height=430, xaxis_title="Periode", yaxis_title="Kriterium")
    return fig


st.image(str(LOGO_PATH), width=260)
st.caption("Trading-Simulation fuer Aktien und Krypto: Watchlist, technische Analyse, Hyperopt und Backtest")
st.warning(DISCLAIMER)

saved_watchlists = list_watchlists()
saved_names = ["Manuelle Eingabe"] + [item["name"] for item in saved_watchlists]

with st.sidebar:
    st.header("Einstellungen")

    selected_watchlist = st.selectbox("Gespeicherte Watchlist", saved_names)
    selected_symbols = DEFAULT_WATCHLIST
    if selected_watchlist != "Manuelle Eingabe":
        selected_symbols = next(item["symbols"] for item in saved_watchlists if item["name"] == selected_watchlist)

    watchlist_text = st.text_area("Watchlist, getrennt mit Komma", value=selected_symbols, height=120)

    watchlist_name = st.text_input("Watchlist speichern als", value=selected_watchlist if selected_watchlist != "Manuelle Eingabe" else "Meine Watchlist")
    if st.button("Watchlist speichern"):
        try:
            save_watchlist(watchlist_name, parse_symbols(watchlist_text))
            st.success("Watchlist gespeichert.")
        except ValueError as exc:
            st.error(str(exc))

    period = st.selectbox("Zeitraum", ["6mo", "1y", "2y", "5y", "10y", "max"], index=3)
    interval = st.selectbox("Intervall", ["1d", "1wk", "1mo"], index=0)
    initial_capital = st.number_input("Startkapital", value=10_000.0, min_value=100.0, step=500.0)
    risk_per_trade = st.slider("Risiko pro Trade", min_value=0.0025, max_value=0.05, value=0.01, step=0.0025)
    fee = st.slider("Gebuehr pro Order", min_value=0.0, max_value=0.01, value=0.001, step=0.0005)
    atr_stop = st.slider("ATR Stop-Loss Faktor", min_value=0.5, max_value=5.0, value=2.0, step=0.25)
    atr_tp = st.slider("ATR Take-Profit Faktor", min_value=0.5, max_value=8.0, value=3.0, step=0.25)
    st.divider()
    enable_hyperopt = st.checkbox("Hyperopt anzeigen", value=True)
    hyperopt_trials = st.slider("Hyperopt Durchlaeufe", min_value=50, max_value=2000, value=500, step=50)
    hyperopt_min_trades = st.number_input("Hyperopt Mindest-Trades", min_value=0, max_value=20, value=1, step=1)
    st.button("Neu berechnen", type="primary")

alerts = recent_alerts()
with st.expander("Neue Signale", expanded=bool(alerts)):
    if alerts:
        st.dataframe(pd.DataFrame(alerts), use_container_width=True)
    else:
        st.info("Noch keine KAUF-Signale gespeichert.")

history = recent_signal_history(50)
with st.expander("Signal-Historie", expanded=False):
    if history:
        st.dataframe(pd.DataFrame(history), use_container_width=True)
    else:
        st.info("Noch keine Signale gespeichert.")

symbols = parse_symbols(watchlist_text)
if not symbols:
    st.error("Keine Symbole eingegeben.")
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
            st.warning(f"{symbol}: Weniger als 220 Tagesdaten. SMA 200 ist nicht sauber belastbar.")

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
    st.error("Keine gueltigen Symbole analysiert.")
    st.write("### Fehleruebersicht")
    st.dataframe(summary_df, use_container_width=True)
    st.info("Pruefe Internetzugriff, Symbolnamen und ob Yahoo Finance erreichbar ist.")
    st.stop()

selected_symbol = st.selectbox("Detailansicht auswaehlen", valid_symbols, index=0)
df = data_cache[selected_symbol]
trades_df = trades_cache[selected_symbol]
equity_df = equity_cache[selected_symbol]
metrics = metrics_cache[selected_symbol]
score = strategy_score(df)

overview_tab, hyperopt_tab, telemetry_tab = st.tabs(["Uebersicht", "Hyperopt", "Simulation"])

with overview_tab:
    st.caption("Die bestehende Detailansicht und der Backtest stehen direkt unter diesen Reitern.")

with telemetry_tab:
    st.subheader(f"Simulation: {selected_symbol}")
    st.caption(
        "Aktiviere nur die Kriterien, die in dieser Simulation beruecksichtigt werden sollen. "
        "Auswertung, Signale und Ranglisten beziehen sich ausschliesslich auf diese Auswahl."
    )

    available_dates = pd.to_datetime(df["Date"]).dt.date
    min_simulation_date = available_dates.min()
    max_simulation_date = available_dates.max()

    st.write("### Zeitfenster")
    date_col1, date_col2 = st.columns(2)
    simulation_start_date = date_col1.date_input(
        "Startdatum",
        value=min_simulation_date,
        min_value=min_simulation_date,
        max_value=max_simulation_date,
        key=f"simulation_start_date_{selected_symbol}",
    )
    simulation_end_date = date_col2.date_input(
        "Enddatum",
        value=max_simulation_date,
        min_value=min_simulation_date,
        max_value=max_simulation_date,
        key=f"simulation_end_date_{selected_symbol}",
    )

    st.write("### Parameter ein- und ausschalten")
    enabled_criteria = []
    toggle_columns = st.columns(3)
    for criterion_index, criterion in enumerate(CRITERIA):
        with toggle_columns[criterion_index % 3]:
            is_enabled = st.checkbox(
                criterion.name,
                value=True,
                key=f"simulation_criterion_{selected_symbol}_{criterion.criterion_id}",
            )
        if is_enabled:
            enabled_criteria.append(criterion.criterion_id)

    if simulation_start_date > simulation_end_date:
        st.error("Das Startdatum muss vor dem Enddatum liegen.")
        simulation_source_df = df.iloc[0:0].copy()
    else:
        simulation_source_df = df[
            (pd.to_datetime(df["Date"]).dt.date >= simulation_start_date)
            & (pd.to_datetime(df["Date"]).dt.date <= simulation_end_date)
        ].copy()
        st.caption(
            f"Simuliertes Zeitfenster: {simulation_start_date} bis {simulation_end_date} "
            f"mit {len(simulation_source_df)} Kurszeilen."
        )

    simulation_df = apply_enabled_criteria_signals(simulation_source_df, enabled_criteria)
    simulation_trades_df, simulation_equity_df = backtest(
        simulation_df,
        initial_capital=initial_capital,
        risk_per_trade=risk_per_trade,
        atr_stop_factor=atr_stop,
        atr_take_profit_factor=atr_tp,
        trading_fee=fee,
    )
    simulation_metrics = calculate_metrics(simulation_trades_df, simulation_equity_df, initial_capital)
    telemetry = build_criterion_telemetry(simulation_df, simulation_trades_df, enabled_criteria)
    summary_telemetry = telemetry["summary"]
    weekly_telemetry = telemetry["weekly"]
    monthly_telemetry = telemetry["monthly"]
    ranking_telemetry = telemetry["ranking"]
    events_telemetry = telemetry["events"]

    if summary_telemetry.empty:
        if not enabled_criteria:
            st.info("Aktiviere mindestens ein Kriterium, damit eine Simulation berechnet werden kann.")
        elif len(simulation_source_df) < 2:
            st.info("Das gewaehlte Zeitfenster enthaelt zu wenig Kursdaten fuer eine Simulation.")
        else:
            st.info("Fuer das gewaehlte Zeitfenster sind noch nicht genug Daten fuer eine Telemetrie-Auswertung vorhanden.")
    else:
        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
        metric_col1.metric("Aktive Kriterien", summary_telemetry["Kriterium"].nunique())
        metric_col2.metric("Auswertungen", int(summary_telemetry["evaluation_count"].sum()))
        metric_col3.metric("Trades", simulation_metrics.get("Abgeschlossene Trades", 0))
        metric_col4.metric("Rendite", f"{simulation_metrics.get('Gesamtrendite %', 0.0):.2f}%")

        st.write("### Simulations-Kennzahlen")
        st.dataframe(format_metrics(simulation_metrics), use_container_width=True)

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
        st.write("### Einzellauf-Auswertung")
        st.dataframe(
            display_summary[
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
            ],
            use_container_width=True,
        )

        st.write("### Ranglisten")
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
            ranking_view[
                [
                    "Kriterium",
                    "Relevanzscore",
                    "Entscheidungseinfluss",
                    "Profit-Score",
                    "Risiko-Score",
                    "Stabilitaet",
                    "Bewertung",
                ]
            ],
            use_container_width=True,
        )

        period_mode = st.radio("Zeitraum fuer Heatmap", ["Wochen", "Monate"], horizontal=True)
        value_column = st.selectbox(
            "Kennzahl",
            [
                "Auswertungen",
                "Ausloeser",
                "Blockierungen",
                "Unterstuetzend",
                "Entscheidende_Ereignisse",
                "Rendite_Pct",
                "Verpasste_Gewinne_Pct",
            ],
        )
        period_df = weekly_telemetry if period_mode == "Wochen" else monthly_telemetry
        st.plotly_chart(make_criterion_heatmap(period_df, value_column, f"{period_mode}: {value_column}"), use_container_width=True)

        st.write("### Wochen- und Monatsaggregate")
        sub_tab_week, sub_tab_month, sub_tab_events = st.tabs(["Wochen", "Monate", "Signalereignisse"])
        with sub_tab_week:
            st.dataframe(weekly_telemetry, use_container_width=True)
        with sub_tab_month:
            st.dataframe(monthly_telemetry, use_container_width=True)
        with sub_tab_events:
            event_view = events_telemetry[events_telemetry["role"] != "none"].copy()
            st.dataframe(event_view.tail(500), use_container_width=True)

        st.download_button(
            "Kriterien-Auswertung als CSV herunterladen",
            summary_telemetry.to_csv(index=False).encode("utf-8"),
            f"{selected_symbol}_kriterien_telemetrie.csv",
            "text/csv",
        )
        st.download_button(
            "Signalereignisse als CSV herunterladen",
            events_telemetry.to_csv(index=False).encode("utf-8"),
            f"{selected_symbol}_kriterien_ereignisse.csv",
            "text/csv",
        )

with overview_tab:
    st.subheader(f"Strategiechart: {selected_symbol}")
    st.plotly_chart(make_chart(df, selected_symbol), use_container_width=True)
    
    st.subheader("Strategieparameter")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Signal", score["signal"])
    col2.metric("Strategie-Score", f"{score['score']}/{score['max_score']}")
    col3.metric("RSI", f"{score['rsi']:.2f}")
    col4.metric("ATR", f"{score['atr']:.2f}")
    
    check_df = pd.DataFrame([{"Kriterium": key, "Erfuellt": "Ja" if value else "Nein"} for key, value in score["checks"].items()])
    st.write("### Kriterienpruefung")
    st.dataframe(check_df, use_container_width=True)
    
    st.write("### Watchlist-Ranking")
    st.dataframe(summary_df, use_container_width=True)
    
    st.write("### Backtest-Kennzahlen")
    st.dataframe(format_metrics(metrics), use_container_width=True)
    
with hyperopt_tab:
    if enable_hyperopt:
        st.write("### Hyperopt")
        st.caption(
            "Optimiert die Parameter aus den Kriterien: SMA, RSI, MACD, Bollinger, Fibonacci, Volumen, Stochastik, ATR, Ichimoku sowie Risiko/Stop/Take-Profit."
        )
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
        }
        st.write("### Kriterien fuer Hyperopt")
        st.caption("Nur angehakte Kriterien werden als Pflichtfilter im Hyperopt verwendet.")
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
            st.warning("Mindestens ein Hyperopt-Kriterium sollte aktiv sein.")

        run_hyperopt_button = st.button("Hyperopt starten", type="primary")
    
        if run_hyperopt_button:
            with st.spinner(f"Optimiere {selected_symbol} mit {hyperopt_trials} Durchlaeufen..."):
                st.session_state["hyperopt_result"] = {
                    "symbol": selected_symbol,
                    "data": run_hyperopt(
                        df,
                        initial_capital=initial_capital,
                        trading_fee=fee,
                        max_trials=hyperopt_trials,
                        min_trades=hyperopt_min_trades,
                        enabled_criteria=hyperopt_criteria,
                    ),
                }
    
        hyperopt_result = st.session_state.get("hyperopt_result")
        if hyperopt_result and hyperopt_result["symbol"] == selected_symbol:
            hyperopt_df = hyperopt_result["data"]
            best_params = best_hyperopt_parameters(hyperopt_df)
    
            if best_params is None:
                st.info("Keine Hyperopt-Ergebnisse vorhanden.")
            else:
                opt_indicator_df = add_indicators(df, best_params.indicator_parameters())
                opt_signal_df = generate_signals(opt_indicator_df, best_params.strategy_parameters(hyperopt_criteria))
                st.write("### Konvergenz")
                st.plotly_chart(make_hyperopt_convergence_chart(hyperopt_df, selected_symbol), use_container_width=True)
                st.write("### Beste Parameter")
                parameter_df = pd.DataFrame(hyperopt_parameter_rows(best_params, hyperopt_criteria, hyperopt_df))
                styled_parameter_df = parameter_df.style.apply(style_hyperopt_parameter_row, axis=1).format(
                    {"Einfluss %": "{:.0f}"}
                )
                st.caption("Einfluss: rot = gering/unwichtig, gelb = mittel, gruen = wichtig im aktuellen Hyperopt-Lauf.")
                st.dataframe(styled_parameter_df, use_container_width=True)
                st.write(f"### Kerzenchart: {selected_symbol}")
                st.plotly_chart(make_candlestick_chart(df, selected_symbol), use_container_width=True)
        else:
            st.info("Klicke auf 'Hyperopt starten', um den ausgewaehlten Detailwert zu optimieren.")
    
with overview_tab:
    if not equity_df.empty:
        st.plotly_chart(make_equity_chart(equity_df, selected_symbol), use_container_width=True)
    
    st.write("### Trades")
    if trades_df.empty:
        st.info("Keine Trades im gewaehlten Zeitraum.")
    else:
        st.dataframe(trades_df, use_container_width=True)
    
    st.download_button("Ranking als CSV herunterladen", summary_df.to_csv(index=False).encode("utf-8"), "watchlist_ranking.csv", "text/csv")
    if not trades_df.empty:
        st.download_button(
            "Trades als CSV herunterladen",
            trades_df.to_csv(index=False).encode("utf-8"),
            f"{selected_symbol}_trades.csv",
            "text/csv",
        )
