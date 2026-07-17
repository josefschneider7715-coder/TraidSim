from __future__ import annotations

from dataclasses import asdict, dataclass
from random import Random

import pandas as pd

from src.backtest import backtest, calculate_metrics
from src.indicators import IndicatorParameters, add_indicators
from src.strategy import StrategyParameters, generate_signals


@dataclass(frozen=True)
class HyperoptParameters:
    sma_trend_period: int
    rsi_period: int
    rsi_min: float
    rsi_max: float
    exit_rsi_max: float
    macd_fast: int
    macd_slow: int
    macd_signal: int
    bb_period: int
    bb_std: float
    fib_lookback: int
    volume_period: int
    volume_factor: float
    stoch_period: int
    stoch_signal: int
    stoch_min: float
    stoch_max: float
    atr_period: int
    atr_min_pct: float
    atr_max_pct: float
    ichimoku_tenkan: int
    ichimoku_kijun: int
    ichimoku_senkou_b: int
    risk_per_trade: float
    atr_stop_factor: float
    atr_take_profit_factor: float

    def indicator_parameters(self) -> IndicatorParameters:
        return IndicatorParameters(
            sma_trend_period=self.sma_trend_period,
            rsi_period=self.rsi_period,
            macd_fast=self.macd_fast,
            macd_slow=self.macd_slow,
            macd_signal=self.macd_signal,
            bb_period=self.bb_period,
            bb_std=self.bb_std,
            fib_lookback=self.fib_lookback,
            volume_period=self.volume_period,
            stoch_period=self.stoch_period,
            stoch_signal=self.stoch_signal,
            atr_period=self.atr_period,
            ichimoku_tenkan=self.ichimoku_tenkan,
            ichimoku_kijun=self.ichimoku_kijun,
            ichimoku_senkou_b=self.ichimoku_senkou_b,
        )

    def strategy_parameters(self, enabled_criteria: dict[str, bool] | None = None) -> StrategyParameters:
        enabled_criteria = enabled_criteria or {
            "trend": True,
            "rsi": True,
            "macd": True,
            "bollinger": True,
            "fibonacci": True,
            "volume": True,
            "stoch": True,
            "atr": True,
            "ichimoku": True,
        }
        return StrategyParameters(
            rsi_min=self.rsi_min,
            rsi_max=self.rsi_max,
            exit_rsi_max=self.exit_rsi_max,
            volume_factor=self.volume_factor,
            stoch_min=self.stoch_min,
            stoch_max=self.stoch_max,
            atr_min_pct=self.atr_min_pct,
            atr_max_pct=self.atr_max_pct,
            use_advanced_filters=True,
            require_trend=enabled_criteria.get("trend", True),
            require_rsi=enabled_criteria.get("rsi", True),
            require_macd=enabled_criteria.get("macd", True),
            require_bollinger=enabled_criteria.get("bollinger", True),
            require_fibonacci=enabled_criteria.get("fibonacci", True),
            require_volume=enabled_criteria.get("volume", True),
            require_stoch=enabled_criteria.get("stoch", True),
            require_atr=enabled_criteria.get("atr", True),
            require_ichimoku=enabled_criteria.get("ichimoku", True),
        )


DEFAULT_SEARCH_SPACE = {
    "sma_trend_period": [30, 50, 75],
    "rsi_period": [10, 14, 21],
    "rsi_min": [35.0, 40.0, 45.0],
    "rsi_max": [60.0, 65.0, 70.0, 75.0],
    "exit_rsi_max": [70.0, 75.0, 80.0],
    "macd_fast": [8, 12, 16],
    "macd_slow": [21, 26, 35],
    "macd_signal": [7, 9, 12],
    "bb_period": [14, 20, 30],
    "bb_std": [1.8, 2.0, 2.2],
    "fib_lookback": [50, 90, 120, 180],
    "volume_period": [10, 20, 30],
    "volume_factor": [0.8, 1.0, 1.2],
    "stoch_period": [10, 14, 21],
    "stoch_signal": [3, 5],
    "stoch_min": [15.0, 20.0, 25.0],
    "stoch_max": [75.0, 80.0, 85.0],
    "atr_period": [10, 14, 21],
    "atr_min_pct": [0.5, 1.0, 1.5],
    "atr_max_pct": [2.0, 4.0, 8.0],
    "ichimoku_tenkan": [7, 9, 12],
    "ichimoku_kijun": [22, 26, 30],
    "ichimoku_senkou_b": [44, 52, 60],
    "risk_per_trade": [0.005, 0.01, 0.015, 0.02],
    "atr_stop_factor": [1.5, 2.0, 2.5, 3.0],
    "atr_take_profit_factor": [2.0, 3.0, 4.0, 5.0],
}


def _candidate_grid(max_trials: int, seed: int = 42) -> list[HyperoptParameters]:
    rng = Random(seed)
    candidates: list[HyperoptParameters] = []
    seen = set()
    default_values = {
        "sma_trend_period": 50,
        "rsi_period": 14,
        "rsi_min": 40.0,
        "rsi_max": 65.0,
        "exit_rsi_max": 75.0,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "bb_period": 20,
        "bb_std": 2.0,
        "fib_lookback": 120,
        "volume_period": 20,
        "volume_factor": 1.0,
        "stoch_period": 14,
        "stoch_signal": 3,
        "stoch_min": 20.0,
        "stoch_max": 80.0,
        "atr_period": 14,
        "atr_min_pct": 1.0,
        "atr_max_pct": 8.0,
        "ichimoku_tenkan": 9,
        "ichimoku_kijun": 26,
        "ichimoku_senkou_b": 52,
        "risk_per_trade": 0.01,
        "atr_stop_factor": 2.0,
        "atr_take_profit_factor": 3.0,
    }
    candidates.append(HyperoptParameters(**default_values))
    seen.add(tuple(default_values.items()))

    while len(candidates) < max_trials:
        candidate_values = {key: rng.choice(values) for key, values in DEFAULT_SEARCH_SPACE.items()}
        if candidate_values["macd_fast"] >= candidate_values["macd_slow"]:
            continue
        if candidate_values["stoch_min"] >= candidate_values["stoch_max"]:
            continue
        if candidate_values["atr_min_pct"] >= candidate_values["atr_max_pct"]:
            continue
        key_tuple = tuple(candidate_values.items())
        if key_tuple in seen:
            continue
        seen.add(key_tuple)
        candidates.append(HyperoptParameters(**candidate_values))

    return candidates


def objective_score(metrics: dict, min_trades: int = 1) -> float:
    total_return = float(metrics.get("Gesamtrendite %", 0.0))
    max_drawdown = abs(float(metrics.get("Max. Drawdown %", 0.0)))
    completed_trades = int(metrics.get("Abgeschlossene Trades", 0))

    if completed_trades < min_trades:
        return -1_000_000.0 + total_return

    return total_return - max_drawdown * 0.5


def run_hyperopt(
    price_df: pd.DataFrame,
    initial_capital: float = 10_000.0,
    trading_fee: float = 0.001,
    risk_per_trade: float = 0.01,
    atr_stop_factor: float = 2.0,
    atr_take_profit_factor: float = 3.0,
    max_trials: int = 100,
    min_trades: int = 1,
    seed: int = 42,
    enabled_criteria: dict[str, bool] | None = None,
) -> pd.DataFrame:
    rows = []
    optimize_risk = enabled_criteria is None or enabled_criteria.get("risk_management", True)

    for trial_number, params in enumerate(_candidate_grid(max_trials=max_trials, seed=seed), start=1):
        trial_risk_per_trade = params.risk_per_trade if optimize_risk else risk_per_trade
        trial_atr_stop_factor = params.atr_stop_factor if optimize_risk else atr_stop_factor
        trial_atr_take_profit_factor = params.atr_take_profit_factor if optimize_risk else atr_take_profit_factor
        indicator_df = add_indicators(price_df, params.indicator_parameters())
        signal_df = generate_signals(indicator_df, params.strategy_parameters(enabled_criteria))
        trades_df, equity_df = backtest(
            signal_df,
            initial_capital=initial_capital,
            risk_per_trade=trial_risk_per_trade,
            atr_stop_factor=trial_atr_stop_factor,
            atr_take_profit_factor=trial_atr_take_profit_factor,
            trading_fee=trading_fee,
        )
        metrics = calculate_metrics(trades_df, equity_df, initial_capital)
        row = asdict(params)
        row.update(
            {
                "risk_per_trade": trial_risk_per_trade,
                "atr_stop_factor": trial_atr_stop_factor,
                "atr_take_profit_factor": trial_atr_take_profit_factor,
            }
        )
        rows.append(
            {
                "Durchlauf": trial_number,
                **row,
                "Objective": objective_score(metrics, min_trades=min_trades),
                "Gesamtrendite %": metrics.get("Gesamtrendite %", 0.0),
                "Max. Drawdown %": metrics.get("Max. Drawdown %", 0.0),
                "Abgeschlossene Trades": metrics.get("Abgeschlossene Trades", 0),
                "Trefferquote %": metrics.get("Trefferquote %", 0.0),
                "Endkapital": metrics.get("Endkapital", initial_capital),
            }
        )

    return pd.DataFrame(rows).sort_values("Objective", ascending=False).reset_index(drop=True)


def best_hyperopt_parameters(results_df: pd.DataFrame) -> HyperoptParameters | None:
    if results_df.empty:
        return None

    row = results_df.iloc[0]
    return HyperoptParameters(
        sma_trend_period=int(row["sma_trend_period"]),
        rsi_period=int(row["rsi_period"]),
        rsi_min=float(row["rsi_min"]),
        rsi_max=float(row["rsi_max"]),
        exit_rsi_max=float(row["exit_rsi_max"]),
        macd_fast=int(row["macd_fast"]),
        macd_slow=int(row["macd_slow"]),
        macd_signal=int(row["macd_signal"]),
        bb_period=int(row["bb_period"]),
        bb_std=float(row["bb_std"]),
        fib_lookback=int(row["fib_lookback"]),
        volume_period=int(row["volume_period"]),
        volume_factor=float(row["volume_factor"]),
        stoch_period=int(row["stoch_period"]),
        stoch_signal=int(row["stoch_signal"]),
        stoch_min=float(row["stoch_min"]),
        stoch_max=float(row["stoch_max"]),
        atr_period=int(row["atr_period"]),
        atr_min_pct=float(row["atr_min_pct"]),
        atr_max_pct=float(row["atr_max_pct"]),
        ichimoku_tenkan=int(row["ichimoku_tenkan"]),
        ichimoku_kijun=int(row["ichimoku_kijun"]),
        ichimoku_senkou_b=int(row["ichimoku_senkou_b"]),
        risk_per_trade=float(row["risk_per_trade"]),
        atr_stop_factor=float(row["atr_stop_factor"]),
        atr_take_profit_factor=float(row["atr_take_profit_factor"]),
    )
