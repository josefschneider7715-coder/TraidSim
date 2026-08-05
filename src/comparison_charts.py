from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def make_strategy_vs_buy_hold_chart(aligned: pd.DataFrame, symbol: str) -> go.Figure:
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.72, 0.28],
        subplot_titles=("Kapitalverlauf", "Laufender Vorteil der Strategie"),
    )
    fig.add_trace(
        go.Scatter(x=aligned["Date"], y=aligned["Strategie"], mode="lines", name="DayTrade-Lab-Strategie"),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=aligned["Date"], y=aligned["Buy and Hold"], mode="lines", name="Buy and Hold"),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=aligned["Date"],
            y=aligned["Vorteil Strategie"],
            mode="lines",
            name="Strategie minus Buy and Hold",
            fill="tozeroy",
        ),
        row=2,
        col=1,
    )
    fig.add_hline(y=0, line_dash="dash", row=2, col=1)
    fig.update_yaxes(title_text="Kapital", row=1, col=1)
    fig.update_yaxes(title_text="Differenz", row=2, col=1)
    fig.update_layout(
        title=f"{symbol} – DayTrade-Lab-Strategie gegen Buy and Hold",
        height=700,
        legend={"orientation": "h"},
        hovermode="x unified",
    )
    return fig


def make_oracle_comparison_chart(aligned: pd.DataFrame, symbol: str, logarithmic: bool = False) -> go.Figure:
    fig = go.Figure()
    for column, label in [
        ("Strategie", "DayTrade-Lab-Strategie"),
        ("Buy and Hold", "Buy and Hold"),
        ("Oracle", "Theoretisches Optimum (Oracle)"),
    ]:
        fig.add_trace(go.Scatter(x=aligned["Date"], y=aligned[column], mode="lines", name=label))
    fig.update_layout(
        title=f"{symbol} – Vergleich mit theoretischem Optimum",
        height=520,
        yaxis_title="Kapital",
        yaxis_type="log" if logarithmic else "linear",
        legend={"orientation": "h"},
        hovermode="x unified",
    )
    return fig


def make_oracle_trade_chart(price_df: pd.DataFrame, oracle_trades: pd.DataFrame, symbol: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=price_df["Date"], y=price_df["Close"], mode="lines", name="Schlusskurs"))
    if not oracle_trades.empty:
        buys = oracle_trades[oracle_trades["Type"] == "BUY"]
        sells = oracle_trades[oracle_trades["Type"] == "SELL"]
        fig.add_trace(
            go.Scatter(
                x=buys["Date"],
                y=buys["Price"],
                mode="markers",
                name="Oracle-Kauf",
                marker={"symbol": "triangle-up", "size": 12},
            )
        )
        fig.add_trace(
            go.Scatter(
                x=sells["Date"],
                y=sells["Price"],
                mode="markers",
                name="Oracle-Verkauf",
                marker={"symbol": "triangle-down", "size": 12},
            )
        )
    fig.update_layout(
        title=f"{symbol} – Rueckblickend optimale Kauf- und Verkaufspunkte",
        height=520,
        yaxis_title="Kurs",
        legend={"orientation": "h"},
        hovermode="x unified",
    )
    return fig
