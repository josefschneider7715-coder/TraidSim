from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.backtest import backtest, calculate_metrics
from src.indicators import add_indicators
from src.strategy import generate_signals
from src.telemetry import apply_enabled_criteria_signals


@dataclass(frozen=True)
class MonteCarloConfig:
    simulations: int = 200
    future_days: int = 252
    seed: int = 42


def _historical_samples(source_df: pd.DataFrame) -> pd.DataFrame:
    clean = source_df.dropna(subset=["Open", "High", "Low", "Close", "Volume"]).copy()
    clean = clean[clean["Close"] > 0].reset_index(drop=True)
    returns = np.log(clean["Close"] / clean["Close"].shift(1)).replace([np.inf, -np.inf], np.nan)
    samples = pd.DataFrame(
        {
            "log_return": returns,
            "high_spread": (clean["High"] / clean[["Open", "Close"]].max(axis=1) - 1).clip(lower=0),
            "low_spread": (clean[["Open", "Close"]].min(axis=1) / clean["Low"] - 1).clip(lower=0),
            "volume": clean["Volume"].clip(lower=0),
        }
    ).dropna()
    return samples


def simulate_future_ohlcv(
    history_df: pd.DataFrame,
    sample_df: pd.DataFrame,
    future_days: int,
    rng: np.random.Generator,
) -> pd.DataFrame:
    last_row = history_df.dropna(subset=["Date", "Close"]).iloc[-1]
    last_close = float(last_row["Close"])
    sampled = sample_df.iloc[rng.integers(0, len(sample_df), size=future_days)].reset_index(drop=True)

    closes = last_close * np.exp(sampled["log_return"].cumsum())
    previous_closes = pd.Series([last_close, *closes.iloc[:-1].tolist()])
    opens = previous_closes.to_numpy()
    highs = np.maximum(opens, closes.to_numpy()) * (1 + sampled["high_spread"].to_numpy())
    lows = np.minimum(opens, closes.to_numpy()) / (1 + sampled["low_spread"].to_numpy())

    dates = pd.bdate_range(pd.to_datetime(last_row["Date"]) + pd.offsets.BDay(1), periods=future_days)
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": closes,
            "Volume": sampled["volume"].to_numpy(),
        }
    )


def _percentile(series: pd.Series, percentile: float) -> float:
    if series.empty:
        return 0.0
    return float(series.quantile(percentile / 100))


def _summary(results_df: pd.DataFrame) -> pd.DataFrame:
    if results_df.empty:
        return pd.DataFrame()

    positive_probability = float((results_df["Strategierendite %"] > 0).mean() * 100)
    buy_hold_probability = float((results_df["Strategierendite %"] > results_df["BuyHold Rendite %"]).mean() * 100)
    drawdown_probability = float((results_df["Max. Drawdown %"] >= -20).mean() * 100)
    trade_probability = float((results_df["Trades"] > 0).mean() * 100)
    robustness_score = np.mean([positive_probability, buy_hold_probability, drawdown_probability, trade_probability])

    return pd.DataFrame(
        [
            {
                "Simulationen": len(results_df),
                "Robustheits-Score %": round(float(robustness_score), 1),
                "Wahrscheinlichkeit Gewinn %": round(positive_probability, 1),
                "Schlaegt Buy-and-Hold %": round(buy_hold_probability, 1),
                "Drawdown besser als -20 %": round(drawdown_probability, 1),
                "Mindestens ein Trade %": round(trade_probability, 1),
                "Median Rendite %": round(float(results_df["Strategierendite %"].median()), 2),
                "Schlechter Fall P5 %": round(_percentile(results_df["Strategierendite %"], 5), 2),
                "Guter Fall P95 %": round(_percentile(results_df["Strategierendite %"], 95), 2),
                "Median Max. Drawdown %": round(float(results_df["Max. Drawdown %"].median()), 2),
            }
        ]
    )


def run_monte_carlo_robustness(
    history_df: pd.DataFrame,
    enabled_criteria: list[str],
    initial_capital: float,
    risk_per_trade: float,
    atr_stop_factor: float,
    atr_take_profit_factor: float,
    trading_fee: float,
    config: MonteCarloConfig,
) -> dict[str, pd.DataFrame]:
    sample_df = _historical_samples(history_df)
    if len(sample_df) < 30 or history_df.empty:
        return {"summary": pd.DataFrame(), "results": pd.DataFrame(), "paths": pd.DataFrame()}

    rng = np.random.default_rng(config.seed)
    warmup_df = history_df.tail(260).copy()
    result_rows = []
    path_rows = []

    for simulation_index in range(1, config.simulations + 1):
        future_raw = simulate_future_ohlcv(warmup_df, sample_df, config.future_days, rng)
        combined_raw = pd.concat([warmup_df, future_raw], ignore_index=True)
        signal_df = apply_enabled_criteria_signals(generate_signals(add_indicators(combined_raw)), enabled_criteria)
        future_signal_df = signal_df.tail(config.future_days + 1).reset_index(drop=True)

        trades_df, equity_df = backtest(
            future_signal_df,
            initial_capital=initial_capital,
            risk_per_trade=risk_per_trade,
            atr_stop_factor=atr_stop_factor,
            atr_take_profit_factor=atr_take_profit_factor,
            trading_fee=trading_fee,
        )
        metrics = calculate_metrics(trades_df, equity_df, initial_capital)
        start_price = float(future_raw["Open"].iloc[0])
        end_price = float(future_raw["Close"].iloc[-1])
        buy_hold_return = (end_price / start_price - 1) * 100 if start_price > 0 else 0.0

        result_rows.append(
            {
                "Pfad": simulation_index,
                "Endkurs": end_price,
                "BuyHold Rendite %": buy_hold_return,
                "Strategierendite %": metrics.get("Gesamtrendite %", 0.0),
                "Max. Drawdown %": metrics.get("Max. Drawdown %", 0.0),
                "Trades": metrics.get("Abgeschlossene Trades", 0),
                "Endkapital": metrics.get("Endkapital", initial_capital),
            }
        )

        if simulation_index <= 30:
            path_rows.extend(
                {
                    "Pfad": simulation_index,
                    "Tag": day_index + 1,
                    "Date": row["Date"],
                    "Close": row["Close"],
                }
                for day_index, row in future_raw.iterrows()
            )

    results_df = pd.DataFrame(result_rows)
    return {
        "summary": _summary(results_df),
        "results": results_df,
        "paths": pd.DataFrame(path_rows),
    }
