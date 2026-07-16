from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


CORE_BUY_CHECKS = [
    "SMA Trend positiv",
    "RSI im Zielbereich",
    "MACD bullisch",
    "Bollinger Momentum positiv",
    "Volumen bestaetigt",
]


@dataclass(frozen=True)
class StrategyParameters:
    rsi_min: float = 40.0
    rsi_max: float = 65.0
    exit_rsi_max: float = 75.0
    volume_factor: float = 1.0
    stoch_min: float = 20.0
    stoch_max: float = 80.0
    atr_min_pct: float = 1.0
    atr_max_pct: float = 8.0
    use_advanced_filters: bool = False
    require_trend: bool = True
    require_rsi: bool = True
    require_macd: bool = True
    require_bollinger: bool = True
    require_fibonacci: bool = False
    require_volume: bool = True
    require_stoch: bool = False
    require_atr: bool = False
    require_ichimoku: bool = False


def generate_signals(df: pd.DataFrame, params: StrategyParameters | None = None) -> pd.DataFrame:
    params = params or StrategyParameters()
    result = df.copy()
    trend_sma = result["SMA_TREND"] if "SMA_TREND" in result.columns else result["SMA_50"]
    volume_sma = result["VOL_SMA"] if "VOL_SMA" in result.columns else result["VOL_SMA_20"]
    cloud_top = result[["ICHIMOKU_SPAN_A", "ICHIMOKU_SPAN_B"]].max(axis=1)
    trend_ok = (result["Close"] > result["SMA_200"]) & (trend_sma > result["SMA_200"])
    rsi_ok = (result["RSI"] > params.rsi_min) & (result["RSI"] < params.rsi_max)
    macd_ok = result["MACD"] > result["MACD_SIGNAL"]
    bollinger_ok = result["Close"] > result["BB_MIDDLE"]
    fib_ok = result["Close"] > result["FIB_618"]
    volume_ok = result["Volume"] > volume_sma * params.volume_factor
    stoch_ok = (result["STOCH_K"] > params.stoch_min) & (result["STOCH_K"] < params.stoch_max) & (result["STOCH_K"] > result["STOCH_D"])
    atr_ok = (result["ATR_PCT"] >= params.atr_min_pct) & (result["ATR_PCT"] <= params.atr_max_pct)
    ichimoku_ok = (result["Close"] > cloud_top) & (result["ICHIMOKU_CONVERSION"] > result["ICHIMOKU_BASE"])
    entry_signal = pd.Series(True, index=result.index)

    if params.require_trend:
        entry_signal = entry_signal & trend_ok & (result["Close"] > trend_sma)
    if params.require_rsi:
        entry_signal = entry_signal & rsi_ok
    if params.require_macd:
        entry_signal = entry_signal & macd_ok
    if params.require_bollinger:
        entry_signal = entry_signal & bollinger_ok
    if params.require_volume:
        entry_signal = entry_signal & volume_ok

    if params.use_advanced_filters or params.require_fibonacci or params.require_stoch or params.require_atr or params.require_ichimoku:
        if params.require_fibonacci:
            entry_signal = entry_signal & fib_ok
        if params.require_stoch:
            entry_signal = entry_signal & stoch_ok
        if params.require_atr:
            entry_signal = entry_signal & atr_ok
        if params.require_ichimoku:
            entry_signal = entry_signal & ichimoku_ok

    result["ENTRY_SIGNAL"] = entry_signal
    result["EXIT_SIGNAL"] = (
        (result["MACD"] < result["MACD_SIGNAL"]) | (result["Close"] < trend_sma) | (result["RSI"] > params.exit_rsi_max)
    )
    return result


def evaluate_latest(df: pd.DataFrame) -> dict:
    clean = df.dropna()

    if clean.empty:
        raise ValueError("Nicht genug Daten fuer Strategie-Score.")

    latest = clean.iloc[-1]
    cloud_top = max(float(latest["ICHIMOKU_SPAN_A"]), float(latest["ICHIMOKU_SPAN_B"]))
    checks = {
        "SMA Trend positiv": bool(latest["Close"] > latest["SMA_50"] and latest["SMA_50"] > latest["SMA_200"]),
        "RSI im Zielbereich": bool(40 < latest["RSI"] < 65),
        "MACD bullisch": bool(latest["MACD"] > latest["MACD_SIGNAL"] and latest["MACD_HIST"] > 0),
        "Bollinger Momentum positiv": bool(latest["Close"] > latest["BB_MIDDLE"]),
        "Fibonacci Unterstuetzung haelt": bool(latest["Close"] > latest["FIB_618"]),
        "Volumen bestaetigt": bool(latest["Volume"] > latest["VOL_SMA_20"]),
        "Stochastik positiv": bool(20 < latest["STOCH_K"] < 80 and latest["STOCH_K"] > latest["STOCH_D"]),
        "ATR Volatilitaet handelbar": bool(1 <= latest["ATR_PCT"] <= 8),
        "Ichimoku bullisch": bool(latest["Close"] > cloud_top and latest["ICHIMOKU_CONVERSION"] > latest["ICHIMOKU_BASE"]),
    }
    core_checks_ok = all(checks[name] for name in CORE_BUY_CHECKS)
    score = sum(checks.values())
    max_score = len(checks)

    if core_checks_ok and score >= 7:
        signal = "KAUF"
    elif latest["Close"] < latest["SMA_200"]:
        signal = "KEIN TRADE / TREND NEGATIV"
    elif latest["Close"] < latest["SMA_50"] or latest["MACD"] < latest["MACD_SIGNAL"]:
        signal = "WARNUNG / WARTEN"
    elif score >= 6:
        signal = "BEOBACHTEN / FAST SETUP"
    else:
        signal = "WARTEN"

    return {
        "date": latest["Date"],
        "close": float(latest["Close"]),
        "rsi": float(latest["RSI"]),
        "atr": float(latest["ATR"]),
        "macd": float(latest["MACD"]),
        "macd_signal": float(latest["MACD_SIGNAL"]),
        "score": int(score),
        "max_score": int(max_score),
        "score_pct": round(score / max_score * 100, 1),
        "signal": signal,
        "checks": checks,
    }
