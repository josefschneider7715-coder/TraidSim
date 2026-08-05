from __future__ import annotations

import pandas as pd

from src.indicators import add_indicators


SIGNAL_COLORS = {
    "KAUFEN": "#16a34a",
    "VERKAUFEN": "#dc2626",
    "BEOBACHTEN": "#d97706",
}


def _latest_with_indicators(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    enriched = add_indicators(frame)
    clean = enriched.dropna(subset=["SMA_20", "SMA_50", "RSI", "MACD", "MACD_SIGNAL", "BB_MIDDLE", "VOL_SMA_20"])
    if clean.empty:
        raise ValueError("Nicht genug Intraday-Kerzen fuer die Monitoranalyse.")
    return enriched, clean.iloc[-1]


def analyze_intraday(timeframe_1h: pd.DataFrame, timeframe_15m: pd.DataFrame, timeframe_5m: pd.DataFrame) -> dict:
    _, hour = _latest_with_indicators(timeframe_1h)
    _, setup = _latest_with_indicators(timeframe_15m)
    _, entry = _latest_with_indicators(timeframe_5m)

    trend_up = bool(hour["Close"] > hour["SMA_50"] and hour["SMA_20"] > hour["SMA_50"])
    trend_down = bool(hour["Close"] < hour["SMA_50"] and hour["SMA_20"] < hour["SMA_50"])
    confirmations = {
        "RSI 40–65": bool(40 < setup["RSI"] < 65),
        "MACD bullisch": bool(setup["MACD"] > setup["MACD_SIGNAL"]),
        "Über Bollinger-Mitte": bool(setup["Close"] > setup["BB_MIDDLE"]),
        "Volumen bestätigt": bool(setup["Volume"] > setup["VOL_SMA_20"]),
    }
    confirmation_count = sum(confirmations.values())
    entry_ready = bool(entry["Close"] > entry["SMA_20"] and entry["MACD"] > entry["MACD_SIGNAL"])

    if trend_down or (setup["Close"] < setup["SMA_50"] and setup["MACD"] < setup["MACD_SIGNAL"]):
        signal = "VERKAUFEN"
        reason = "Abwärtstrend oder bearischer 15-Minuten-Ausstieg"
    elif trend_up and confirmation_count >= 3 and entry_ready:
        signal = "KAUFEN"
        reason = "1-Stunden-Trend, mindestens 3 Bestätigungen und 5-Minuten-Einstieg sind positiv"
    else:
        signal = "BEOBACHTEN"
        reason = "Noch nicht alle Zeitebenen bestätigen den Einstieg"

    return {
        "signal": signal,
        "color": SIGNAL_COLORS[signal],
        "reason": reason,
        "price": float(entry["Close"]),
        "rsi_15m": float(setup["RSI"]),
        "trend_1h": "Aufwärts" if trend_up else "Abwärts" if trend_down else "Seitwärts",
        "confirmations": confirmations,
        "confirmation_count": confirmation_count,
        "entry_5m": entry_ready,
        "updated_at": pd.to_datetime(entry["Date"]),
        "values": {
            "1h": {
                "Kurs": float(hour["Close"]),
                "SMA 20": float(hour["SMA_20"]),
                "SMA 50": float(hour["SMA_50"]),
            },
            "15m": {
                "RSI": float(setup["RSI"]),
                "MACD": float(setup["MACD"]),
                "MACD-Signallinie": float(setup["MACD_SIGNAL"]),
                "Kurs": float(setup["Close"]),
                "Bollinger-Mitte": float(setup["BB_MIDDLE"]),
                "Volumen": float(setup["Volume"]),
                "Volumen-SMA 20": float(setup["VOL_SMA_20"]),
            },
            "5m": {
                "Kurs": float(entry["Close"]),
                "SMA 20": float(entry["SMA_20"]),
                "MACD": float(entry["MACD"]),
                "MACD-Signallinie": float(entry["MACD_SIGNAL"]),
                "ATR": float(entry["ATR"]),
            },
        },
    }


def simulate_current_day(frame_5m: pd.DataFrame, initial_capital: float, fee: float) -> pd.DataFrame:
    enriched = add_indicators(frame_5m).copy()
    dates = pd.to_datetime(enriched["Date"])
    latest_day = dates.dt.date.max()
    active = (
        (enriched["Close"] > enriched["SMA_20"])
        & (enriched["SMA_20"] > enriched["SMA_50"])
        & (enriched["MACD"] > enriched["MACD_SIGNAL"])
        & enriched["RSI"].between(40, 70)
    ).fillna(False)
    position = active.shift(1, fill_value=False).astype(float)
    returns = enriched["Close"].pct_change().fillna(0.0)
    changes = position.diff().abs().fillna(position.abs())
    strategy_returns = position * returns - changes * float(fee)
    enriched["Equity"] = float(initial_capital) * (1.0 + strategy_returns).cumprod()
    enriched["Gewinn"] = enriched["Equity"] - float(initial_capital)
    enriched["Position"] = position
    result = enriched.loc[dates.dt.date == latest_day, ["Date", "Equity", "Gewinn", "Position"]].copy()
    if result.empty:
        raise ValueError("Keine 5-Minuten-Kerzen fuer den aktuellen Handelstag vorhanden.")
    return result.reset_index(drop=True)
