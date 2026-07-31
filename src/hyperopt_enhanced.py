from __future__ import annotations

from dataclasses import asdict

import pandas as pd

from src.backtest import backtest, calculate_metrics
from src.hyperopt import HyperoptParameters, _candidate_grid, best_hyperopt_parameters
from src.indicators import add_indicators
from src.strategy import generate_signals


OBJECTIVE_LABELS = {
    "max_profit": "Maximaler Gewinn",
    "risk_adjusted": "Gewinn minus Drawdown",
    "balanced": "Rendite, Drawdown und Gebühren",
}


def _enabled(enabled_criteria: dict[str, bool] | None, key: str, default: bool = True) -> bool:
    if enabled_criteria is None:
        return default
    return bool(enabled_criteria.get(key, default))


def apply_hyperopt_scored_signals(
    indicator_df: pd.DataFrame,
    params: HyperoptParameters,
    enabled_criteria: dict[str, bool] | None,
    minimum_confirmations: int = 3,
) -> pd.DataFrame:
    """Verwendet dieselbe Logik wie die Simulation: Trend plus Bestätigungen.

    Die Schwellen und Perioden stammen dabei aus dem jeweiligen Hyperopt-Durchlauf.
    Die vorhandenen Exit-Regeln werden aus generate_signals übernommen.
    """
    result = generate_signals(indicator_df, params.strategy_parameters(enabled_criteria))
    trend_sma = result["SMA_TREND"] if "SMA_TREND" in result.columns else result["SMA_50"]
    volume_sma = result["VOL_SMA"] if "VOL_SMA" in result.columns else result["VOL_SMA_20"]
    cloud_top = result[["ICHIMOKU_SPAN_A", "ICHIMOKU_SPAN_B"]].max(axis=1)

    checks = {
        "trend": (result["Close"] > trend_sma) & (trend_sma > result["SMA_200"]),
        "rsi": (result["RSI"] > params.rsi_min) & (result["RSI"] < params.rsi_max),
        "macd": (result["MACD"] > result["MACD_SIGNAL"]) & (result["MACD_HIST"] > 0),
        "bollinger": result["Close"] > result["BB_MIDDLE"],
        "fibonacci": result["Close"] > result["FIB_618"],
        "volume": result["Volume"] > volume_sma * params.volume_factor,
        "stoch": (
            (result["STOCH_K"] > params.stoch_min)
            & (result["STOCH_K"] < params.stoch_max)
            & (result["STOCH_K"] > result["STOCH_D"])
        ),
        "atr": (result["ATR_PCT"] >= params.atr_min_pct) & (result["ATR_PCT"] <= params.atr_max_pct),
        "ichimoku": (result["Close"] > cloud_top)
        & (result["ICHIMOKU_CONVERSION"] > result["ICHIMOKU_BASE"]),
    }

    active_keys = [
        key
        for key in ["trend", "rsi", "macd", "bollinger", "fibonacci", "volume", "stoch", "atr", "ichimoku"]
        if _enabled(enabled_criteria, key)
    ]
    confirmation_keys = [key for key in active_keys if key != "trend"]
    trend_required = "trend" in active_keys

    if confirmation_keys:
        confirmation_frame = pd.concat([checks[key].fillna(False).rename(key) for key in confirmation_keys], axis=1)
        confirmation_count = confirmation_frame.sum(axis=1).astype(int)
        required = min(max(1, int(minimum_confirmations)), len(confirmation_keys))
        confirmation_ok = confirmation_count >= required
    else:
        confirmation_count = pd.Series(0, index=result.index, dtype=int)
        required = 0
        confirmation_ok = pd.Series(True, index=result.index)

    trend_ok = checks["trend"].fillna(False) if trend_required else pd.Series(True, index=result.index)
    result["ENTRY_SIGNAL"] = (trend_ok & confirmation_ok).fillna(False)
    result["ENTRY_CONFIRMATIONS"] = confirmation_count
    result["ENTRY_REQUIRED_CONFIRMATIONS"] = required
    result["ENTRY_TREND_REQUIRED"] = trend_required
    return result


def _fees_total(trades_df: pd.DataFrame, trading_fee: float) -> float:
    if trades_df is None or trades_df.empty:
        return 0.0
    required = {"Price", "Units"}
    if not required.issubset(trades_df.columns):
        return 0.0
    return float((trades_df["Price"].astype(float) * trades_df["Units"].astype(float) * float(trading_fee)).sum())


def objective_score(
    metrics: dict,
    fees_total: float,
    initial_capital: float,
    objective_mode: str = "risk_adjusted",
    min_trades: int = 1,
) -> float:
    total_return = float(metrics.get("Gesamtrendite %", 0.0))
    max_drawdown = abs(float(metrics.get("Max. Drawdown %", 0.0)))
    completed_trades = int(metrics.get("Abgeschlossene Trades", 0))
    fee_pct = float(fees_total) / max(float(initial_capital), 0.01) * 100

    if completed_trades < min_trades:
        return -1_000_000.0 + total_return
    if objective_mode == "max_profit":
        return total_return
    if objective_mode == "balanced":
        return total_return - 0.5 * max_drawdown - fee_pct
    return total_return - 0.5 * max_drawdown


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
    objective_mode: str = "risk_adjusted",
    minimum_confirmations: int = 3,
) -> pd.DataFrame:
    if objective_mode not in OBJECTIVE_LABELS:
        raise ValueError(f"Unbekanntes Optimierungsziel: {objective_mode}")

    rows: list[dict] = []
    optimize_risk = enabled_criteria is None or enabled_criteria.get("risk_management", True)

    for trial_number, params in enumerate(_candidate_grid(max_trials=max_trials, seed=seed), start=1):
        trial_risk = params.risk_per_trade if optimize_risk else risk_per_trade
        trial_stop = params.atr_stop_factor if optimize_risk else atr_stop_factor
        trial_take_profit = params.atr_take_profit_factor if optimize_risk else atr_take_profit_factor

        indicator_df = add_indicators(price_df, params.indicator_parameters())
        signal_df = apply_hyperopt_scored_signals(
            indicator_df,
            params,
            enabled_criteria,
            minimum_confirmations=minimum_confirmations,
        )
        trades_df, equity_df = backtest(
            signal_df,
            initial_capital=initial_capital,
            risk_per_trade=trial_risk,
            atr_stop_factor=trial_stop,
            atr_take_profit_factor=trial_take_profit,
            trading_fee=trading_fee,
        )
        metrics = calculate_metrics(trades_df, equity_df, initial_capital)
        fees_total = _fees_total(trades_df, trading_fee)
        fee_pct = fees_total / max(float(initial_capital), 0.01) * 100
        parameter_values = asdict(params)
        parameter_values.update(
            {
                "risk_per_trade": trial_risk,
                "atr_stop_factor": trial_stop,
                "atr_take_profit_factor": trial_take_profit,
            }
        )
        rows.append(
            {
                "Durchlauf": trial_number,
                **parameter_values,
                "Optimierungsziel": OBJECTIVE_LABELS[objective_mode],
                "Objective": objective_score(
                    metrics,
                    fees_total=fees_total,
                    initial_capital=initial_capital,
                    objective_mode=objective_mode,
                    min_trades=min_trades,
                ),
                "Gesamtrendite %": metrics.get("Gesamtrendite %", 0.0),
                "Max. Drawdown %": metrics.get("Max. Drawdown %", 0.0),
                "Abgeschlossene Trades": metrics.get("Abgeschlossene Trades", 0),
                "Trefferquote %": metrics.get("Trefferquote %", 0.0),
                "Gebuehren gesamt": fees_total,
                "Gebuehren %": fee_pct,
                "Endkapital": metrics.get("Endkapital", initial_capital),
            }
        )

    return pd.DataFrame(rows).sort_values("Objective", ascending=False).reset_index(drop=True)


def parameter_importance(results_df: pd.DataFrame, target_column: str) -> pd.DataFrame:
    """Misst die Ergebnisspanne der mittleren Zielgröße je Parameterwert."""
    if results_df.empty or target_column not in results_df.columns:
        return pd.DataFrame(columns=["Parameter", "Einfluss %", "Ergebnisspanne"])

    valid = results_df[results_df["Objective"] > -999_000].copy()
    ignored = {
        "Durchlauf",
        "Optimierungsziel",
        "Objective",
        "Gesamtrendite %",
        "Max. Drawdown %",
        "Abgeschlossene Trades",
        "Trefferquote %",
        "Gebuehren gesamt",
        "Gebuehren %",
        "Endkapital",
    }
    rows = []
    for column in valid.columns:
        if column in ignored or valid[column].nunique(dropna=True) < 2:
            continue
        means = valid.groupby(column, dropna=True)[target_column].mean()
        if len(means) < 2:
            continue
        spread = float(means.max() - means.min())
        best_value = means.idxmax()
        rows.append({"Parameter": column, "Ergebnisspanne": spread, "Bester Wert": best_value})

    result = pd.DataFrame(rows)
    if result.empty:
        return pd.DataFrame(columns=["Parameter", "Einfluss %", "Ergebnisspanne", "Bester Wert"])
    maximum = float(result["Ergebnisspanne"].max())
    result["Einfluss %"] = result["Ergebnisspanne"] / maximum * 100 if maximum > 0 else 0.0
    return result.sort_values("Einfluss %", ascending=False).reset_index(drop=True)


def profit_parameter_importance(results_df: pd.DataFrame) -> pd.DataFrame:
    return parameter_importance(results_df, "Gesamtrendite %")


__all__ = [
    "HyperoptParameters",
    "OBJECTIVE_LABELS",
    "apply_hyperopt_scored_signals",
    "best_hyperopt_parameters",
    "objective_score",
    "parameter_importance",
    "profit_parameter_importance",
    "run_hyperopt",
]
