from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def _format_price(value: float) -> str:
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _format_volume(value: float) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:.0f}"


def _add_status_box(fig, y: float, title: str, value: str, upper: str, lower: str, is_ok: bool) -> None:
    color = "#22c55e" if is_ok else "#ef4444"
    fig.add_annotation(
        x=-0.075,
        y=y,
        xref="paper",
        yref="paper",
        xanchor="center",
        yanchor="middle",
        showarrow=False,
        align="center",
        borderwidth=0,
        borderpad=0,
        bgcolor="rgba(0, 0, 0, 0)",
        font={"size": 12, "color": "#e5e7eb"},
        text=(
            f"<b>{title}</b><br>"
            f"<span style='font-size:11px;color:#94a3b8'>{upper}</span><br>"
            f"<span style='font-size:18px;color:{color}'><b>{value}</b></span><br>"
            f"<span style='font-size:11px;color:#94a3b8'>{lower}</span>"
        ),
    )


def _add_latest_status(fig, df: pd.DataFrame) -> None:
    clean = df.dropna()
    if clean.empty:
        return

    latest = clean.iloc[-1]
    close = float(latest["Close"])
    sma_50 = float(latest["SMA_50"])
    sma_200 = float(latest["SMA_200"])
    rsi = float(latest["RSI"])
    macd = float(latest["MACD"])
    macd_signal = float(latest["MACD_SIGNAL"])
    volume = float(latest["Volume"])
    volume_sma = float(latest["VOL_SMA_20"])
    stoch_k = float(latest["STOCH_K"])
    stoch_d = float(latest["STOCH_D"])

    trend_ok = close > sma_50 and close > sma_200 and sma_50 > sma_200
    rsi_ok = 40 < rsi < 65
    stoch_ok = 20 < stoch_k < 80 and stoch_k > stoch_d
    macd_ok = macd > macd_signal
    volume_ok = volume > volume_sma

    _add_status_box(
        fig,
        0.82,
        "Kurs",
        _format_price(close),
        f"SMA50 {_format_price(sma_50)}",
        f"SMA200 {_format_price(sma_200)}",
        trend_ok,
    )
    _add_status_box(fig, 0.42, "RSI", f"{rsi:.1f}", "max 65", "min 40", rsi_ok)
    _add_status_box(fig, 0.30, "Stoch", f"{stoch_k:.1f}", "%K > %D", f"%D {stoch_d:.1f}", stoch_ok)
    _add_status_box(
        fig,
        0.19,
        "MACD",
        f"{macd:.2f}",
        "MACD > Signal",
        f"Signal {macd_signal:.2f}",
        macd_ok,
    )
    _add_status_box(
        fig,
        0.07,
        "Volumen",
        _format_volume(volume),
        "Vol > SMA20",
        f"SMA20 {_format_volume(volume_sma)}",
        volume_ok,
    )


def make_chart(df: pd.DataFrame, symbol: str):
    fig = make_subplots(
        rows=5,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.46, 0.14, 0.14, 0.14, 0.12],
        subplot_titles=("Kurs mit SMA, Bollinger, Fibonacci und Ichimoku", "RSI", "Stochastik", "MACD", "Volumen"),
    )

    fig.add_trace(
        go.Candlestick(x=df["Date"], open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="Kerzen"),
        row=1,
        col=1,
    )

    for column, label in [
        ("SMA_20", "SMA 20"),
        ("SMA_50", "SMA 50"),
        ("SMA_200", "SMA 200"),
        ("BB_UPPER", "BB oben"),
        ("BB_LOWER", "BB unten"),
        ("FIB_382", "Fibonacci 38,2%"),
        ("FIB_500", "Fibonacci 50,0%"),
        ("FIB_618", "Fibonacci 61,8%"),
        ("ICHIMOKU_CONVERSION", "Ichimoku Conversion"),
        ("ICHIMOKU_BASE", "Ichimoku Base"),
    ]:
        fig.add_trace(go.Scatter(x=df["Date"], y=df[column], name=label, mode="lines"), row=1, col=1)

    fig.add_trace(
        go.Scatter(
            x=df["Date"],
            y=df["ICHIMOKU_SPAN_A"],
            name="Ichimoku Wolke A",
            mode="lines",
            line={"width": 0.5, "color": "rgba(34, 197, 94, 0.45)"},
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df["Date"],
            y=df["ICHIMOKU_SPAN_B"],
            name="Ichimoku Wolke B",
            mode="lines",
            fill="tonexty",
            fillcolor="rgba(34, 197, 94, 0.12)",
            line={"width": 0.5, "color": "rgba(239, 68, 68, 0.45)"},
        ),
        row=1,
        col=1,
    )

    buys = df[df["ENTRY_SIGNAL"]]
    exits = df[df["EXIT_SIGNAL"]]
    fig.add_trace(
        go.Scatter(
            x=buys["Date"],
            y=buys["Close"],
            mode="markers",
            name="Kaufsignal",
            marker={"symbol": "triangle-up", "size": 12, "color": "#1f9d55"},
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=exits["Date"],
            y=exits["Close"],
            mode="markers",
            name="Exit-Signal",
            marker={"symbol": "triangle-down", "size": 10, "color": "#d64545"},
        ),
        row=1,
        col=1,
    )

    fig.add_trace(go.Scatter(x=df["Date"], y=df["RSI"], name="RSI", mode="lines"), row=2, col=1)
    fig.add_hline(y=70, line_dash="dash", row=2, col=1)
    fig.add_hline(y=40, line_dash="dash", row=2, col=1)

    fig.add_trace(go.Scatter(x=df["Date"], y=df["STOCH_K"], name="Stoch %K", mode="lines"), row=3, col=1)
    fig.add_trace(go.Scatter(x=df["Date"], y=df["STOCH_D"], name="Stoch %D", mode="lines"), row=3, col=1)
    fig.add_hline(y=80, line_dash="dash", row=3, col=1)
    fig.add_hline(y=20, line_dash="dash", row=3, col=1)

    fig.add_trace(go.Scatter(x=df["Date"], y=df["MACD"], name="MACD", mode="lines"), row=4, col=1)
    fig.add_trace(go.Scatter(x=df["Date"], y=df["MACD_SIGNAL"], name="MACD Signal", mode="lines"), row=4, col=1)
    fig.add_trace(go.Bar(x=df["Date"], y=df["MACD_HIST"], name="MACD Histogramm"), row=4, col=1)
    fig.add_trace(go.Bar(x=df["Date"], y=df["Volume"], name="Volumen"), row=5, col=1)
    fig.add_trace(go.Scatter(x=df["Date"], y=df["VOL_SMA_20"], name="Volumen SMA 20", mode="lines"), row=5, col=1)
    _add_latest_status(fig, df)
    fig.update_layout(
        title=f"{symbol} - Strategiechart",
        height=950,
        margin={"l": 165, "r": 35, "t": 70, "b": 80},
        xaxis_rangeslider_visible=False,
        legend={"orientation": "h"},
    )
    return fig


def make_candlestick_chart(df: pd.DataFrame, symbol: str):
    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=df["Date"],
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="Kerzen",
        )
    )
    fig.update_layout(
        title=f"{symbol} - Kurs",
        height=620,
        margin={"l": 45, "r": 35, "t": 70, "b": 45},
        xaxis_rangeslider_visible=False,
        yaxis_title="Kurs",
        legend={"orientation": "h"},
    )
    return fig


def make_equity_chart(equity_df: pd.DataFrame, symbol: str):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=equity_df["Date"], y=equity_df["Equity"], mode="lines", name="Strategie"))
    fig.update_layout(title=f"{symbol} - Equity Curve", height=420)
    return fig


def make_hyperopt_convergence_chart(results_df: pd.DataFrame, symbol: str):
    ordered = results_df.sort_index().copy()
    ordered["Durchlauf"] = range(1, len(ordered) + 1)
    ordered["Bester Objective"] = ordered["Objective"].cummax()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=ordered["Durchlauf"],
            y=ordered["Objective"],
            mode="lines+markers",
            name="Objective je Durchlauf",
            marker={"size": 5, "color": "rgba(148, 163, 184, 0.65)"},
            line={"color": "rgba(148, 163, 184, 0.45)", "width": 1},
            hovertemplate="Durchlauf %{x}<br>Objective %{y:.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=ordered["Durchlauf"],
            y=ordered["Bester Objective"],
            mode="lines",
            name="Bester Wert bis dahin",
            line={"color": "#22c55e", "width": 3},
            hovertemplate="Durchlauf %{x}<br>Bester Objective %{y:.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        title=f"{symbol} - Hyperopt Konvergenz",
        height=380,
        xaxis_title="Durchlauf",
        yaxis_title="Objective",
        legend={"orientation": "h"},
    )
    return fig
