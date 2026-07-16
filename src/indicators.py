from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class IndicatorParameters:
    sma_trend_period: int = 50
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bb_period: int = 20
    bb_std: float = 2.0
    fib_lookback: int = 120
    volume_period: int = 20
    stoch_period: int = 14
    stoch_signal: int = 3
    atr_period: int = 14
    ichimoku_tenkan: int = 9
    ichimoku_kijun: int = 26
    ichimoku_senkou_b: int = 52


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi_wilder(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    result = 100 - (100 / (1 + rs))
    return result.fillna(50).clip(0, 100)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[pd.Series, pd.Series, pd.Series]:
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def bollinger_bands(close: pd.Series, period: int = 20, std_factor: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    middle = close.rolling(period).mean()
    std = close.rolling(period).std()
    return middle + std_factor * std, middle, middle - std_factor * std


def atr_wilder(df: pd.DataFrame, period: int = 14) -> pd.Series:
    previous_close = df["Close"].shift(1)
    tr1 = df["High"] - df["Low"]
    tr2 = (df["High"] - previous_close).abs()
    tr3 = (df["Low"] - previous_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def fibonacci_levels(df: pd.DataFrame, period: int = 120) -> tuple[pd.Series, pd.Series, pd.Series]:
    high = df["High"].rolling(period).max()
    low = df["Low"].rolling(period).min()
    span = high - low
    fib_382 = high - span * 0.382
    fib_500 = high - span * 0.500
    fib_618 = high - span * 0.618
    return fib_382, fib_500, fib_618


def stochastic_oscillator(df: pd.DataFrame, period: int = 14, signal: int = 3) -> tuple[pd.Series, pd.Series]:
    lowest_low = df["Low"].rolling(period).min()
    highest_high = df["High"].rolling(period).max()
    percent_k = 100 * (df["Close"] - lowest_low) / (highest_high - lowest_low).replace(0, np.nan)
    percent_d = percent_k.rolling(signal).mean()
    return percent_k.fillna(50).clip(0, 100), percent_d.fillna(50).clip(0, 100)


def ichimoku_cloud(
    df: pd.DataFrame,
    tenkan_period: int = 9,
    kijun_period: int = 26,
    senkou_b_period: int = 52,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    high_tenkan = df["High"].rolling(tenkan_period).max()
    low_tenkan = df["Low"].rolling(tenkan_period).min()
    conversion = (high_tenkan + low_tenkan) / 2

    high_kijun = df["High"].rolling(kijun_period).max()
    low_kijun = df["Low"].rolling(kijun_period).min()
    base = (high_kijun + low_kijun) / 2

    span_a = (conversion + base) / 2
    high_senkou_b = df["High"].rolling(senkou_b_period).max()
    low_senkou_b = df["Low"].rolling(senkou_b_period).min()
    span_b = (high_senkou_b + low_senkou_b) / 2
    return conversion, base, span_a, span_b


def add_indicators(df: pd.DataFrame, params: IndicatorParameters | None = None) -> pd.DataFrame:
    params = params or IndicatorParameters()
    result = df.copy()
    result["SMA_20"] = sma(result["Close"], 20)
    result["SMA_50"] = sma(result["Close"], 50)
    result["SMA_200"] = sma(result["Close"], 200)
    result["SMA_TREND"] = sma(result["Close"], params.sma_trend_period)
    result["RSI"] = rsi_wilder(result["Close"], params.rsi_period)
    result["MACD"], result["MACD_SIGNAL"], result["MACD_HIST"] = macd(
        result["Close"], params.macd_fast, params.macd_slow, params.macd_signal
    )
    result["BB_UPPER"], result["BB_MIDDLE"], result["BB_LOWER"] = bollinger_bands(result["Close"], params.bb_period, params.bb_std)
    result["ATR"] = atr_wilder(result, params.atr_period)
    result["ATR_PCT"] = result["ATR"] / result["Close"] * 100
    result["VOL_SMA_20"] = sma(result["Volume"], 20)
    result["VOL_SMA"] = sma(result["Volume"], params.volume_period)
    result["FIB_382"], result["FIB_500"], result["FIB_618"] = fibonacci_levels(result, params.fib_lookback)
    result["STOCH_K"], result["STOCH_D"] = stochastic_oscillator(result, params.stoch_period, params.stoch_signal)
    (
        result["ICHIMOKU_CONVERSION"],
        result["ICHIMOKU_BASE"],
        result["ICHIMOKU_SPAN_A"],
        result["ICHIMOKU_SPAN_B"],
    ) = ichimoku_cloud(result, params.ichimoku_tenkan, params.ichimoku_kijun, params.ichimoku_senkou_b)
    return result
