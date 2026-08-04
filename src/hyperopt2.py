from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.backtest import backtest, buy_and_hold_metrics, calculate_metrics
from src.hyperopt import HyperoptParameters, _candidate_grid, best_hyperopt_parameters
from src.indicators import add_indicators
from src.strategy import generate_signals


OBJECTIVES = {
    "balanced": "Ausgewogen",
    "return": "Maximale Rendite",
    "drawdown": "Minimaler Drawdown",
    "win_rate": "Maximale Trefferquote",
    "risk_adjusted": "Risikoadjustiert",
}

METRIC_COLUMNS = {
    "Durchlauf",
    "Objective",
    "Gesamtrendite %",
    "Max. Drawdown %",
    "Abgeschlossene Trades",
    "Trefferquote %",
    "Endkapital",
}


@dataclass(frozen=True)
class Hyperopt2Result:
    trials: pd.DataFrame
    importance: pd.DataFrame
    sensitivity: pd.DataFrame
    heatmap: pd.DataFrame
    benchmarks: pd.DataFrame
    stability_index: float
    evaluation: str


def objective_score(metrics: dict, objective: str = "balanced", min_trades: int = 1) -> float:
    if objective not in OBJECTIVES:
        raise ValueError(f"Unbekanntes Optimierungsziel: {objective}")

    total_return = float(metrics.get("Gesamtrendite %", 0.0))
    drawdown = abs(float(metrics.get("Max. Drawdown %", 0.0)))
    win_rate = float(metrics.get("Trefferquote %", 0.0))
    trades = int(metrics.get("Abgeschlossene Trades", 0))
    if trades < min_trades:
        return -1_000_000.0 + total_return

    if objective == "return":
        return total_return
    if objective == "drawdown":
        return -drawdown + min(total_return, 0.0)
    if objective == "win_rate":
        return win_rate + total_return * 0.05
    if objective == "risk_adjusted":
        return total_return / max(drawdown, 1.0)
    return total_return - drawdown * 0.5 + win_rate * 0.05


def _oracle_metrics(price_df: pd.DataFrame, initial_capital: float) -> dict[str, float]:
    close = pd.to_numeric(price_df["Close"], errors="coerce").dropna()
    if len(close) < 2:
        return {"Oracle Rendite %": 0.0, "Oracle Endkapital": initial_capital}
    positive_growth = (1.0 + close.pct_change().clip(lower=0.0).fillna(0.0)).prod()
    return {
        "Oracle Rendite %": float((positive_growth - 1.0) * 100.0),
        "Oracle Endkapital": float(initial_capital * positive_growth),
    }


def _parameter_columns(trials: pd.DataFrame) -> list[str]:
    return [
        column
        for column in trials.columns
        if column not in METRIC_COLUMNS and pd.api.types.is_numeric_dtype(trials[column])
    ]


def parameter_importance(trials: pd.DataFrame) -> pd.DataFrame:
    valid = trials[trials["Objective"] > -999_000].copy() if not trials.empty else trials
    if len(valid) < 3 or valid["Objective"].nunique() < 2:
        return pd.DataFrame(columns=["Parameter", "Importance %"])

    scores: list[dict] = []
    for parameter in _parameter_columns(valid):
        if valid[parameter].nunique() < 2:
            continue
        means = valid.groupby(parameter)["Objective"].mean()
        spread = float(means.max() - means.min())
        correlation = abs(float(valid[[parameter, "Objective"]].corr(method="spearman").iloc[0, 1]))
        if np.isnan(correlation):
            correlation = 0.0
        scores.append({"Parameter": parameter, "raw": spread * (0.5 + correlation)})

    total = sum(item["raw"] for item in scores)
    for item in scores:
        item["Importance %"] = item["raw"] / total * 100.0 if total else 0.0
    return pd.DataFrame(scores).drop(columns="raw", errors="ignore").sort_values("Importance %", ascending=False).reset_index(drop=True)


def sensitivity_data(trials: pd.DataFrame, importance: pd.DataFrame, top_n: int = 6) -> pd.DataFrame:
    valid = trials[trials["Objective"] > -999_000].copy() if not trials.empty else trials
    rows: list[dict] = []
    for parameter in importance.head(top_n).get("Parameter", []):
        grouped = valid.groupby(parameter)["Objective"].agg(["mean", "std", "count"]).reset_index()
        for _, row in grouped.iterrows():
            rows.append(
                {
                    "Parameter": parameter,
                    "Wert": row[parameter],
                    "Objective Mittel": float(row["mean"]),
                    "Objective Std": float(0.0 if pd.isna(row["std"]) else row["std"]),
                    "Versuche": int(row["count"]),
                }
            )
    return pd.DataFrame(
        rows,
        columns=["Parameter", "Wert", "Objective Mittel", "Objective Std", "Versuche"],
    )


def heatmap_data(trials: pd.DataFrame, importance: pd.DataFrame) -> pd.DataFrame:
    parameters = importance.head(2).get("Parameter", []).tolist()
    if len(parameters) < 2:
        return pd.DataFrame()
    valid = trials[trials["Objective"] > -999_000]
    return valid.pivot_table(index=parameters[0], columns=parameters[1], values="Objective", aggfunc="mean")


def stability_index(trials: pd.DataFrame) -> float:
    valid = trials[trials["Objective"] > -999_000].copy() if not trials.empty else trials
    if len(valid) < 3:
        return 0.0
    top_count = max(3, int(np.ceil(len(valid) * 0.2)))
    top = valid.nlargest(top_count, "Objective")
    objective_mean = abs(float(top["Objective"].mean()))
    objective_cv = float(top["Objective"].std(ddof=0)) / max(objective_mean, 1.0)
    return_score = max(0.0, 100.0 - min(objective_cv * 100.0, 100.0))
    positive_ratio = float((top["Gesamtrendite %"] > 0).mean()) * 100.0
    drawdown_score = max(0.0, 100.0 - abs(float(top["Max. Drawdown %"].mean())) * 2.0)
    return round(return_score * 0.5 + positive_ratio * 0.3 + drawdown_score * 0.2, 1)


def _evaluation(best: pd.Series, benchmarks: pd.DataFrame, stability: float) -> str:
    buy_hold = float(benchmarks.loc[benchmarks["Vergleich"] == "Buy & Hold", "Rendite %"].iloc[0])
    strategy = float(best["Gesamtrendite %"])
    verdict = "robust" if stability >= 70 else "brauchbar, aber sensitiv" if stability >= 45 else "instabil"
    comparison = "schlaegt" if strategy > buy_hold else "unterschreitet"
    return (
        f"Die beste Konfiguration ist {verdict} (Stabilitaetsindex {stability:.1f}/100) und "
        f"{comparison} Buy & Hold um {abs(strategy - buy_hold):.2f} Prozentpunkte. "
        "Vor einem produktiven Einsatz sollten Walk-forward-Tests auf ungesehenen Zeitraeumen folgen."
    )


def run_hyperopt2(
    price_df: pd.DataFrame,
    initial_capital: float = 10_000.0,
    trading_fee: float = 0.001,
    risk_per_trade: float = 0.01,
    atr_stop_factor: float = 2.0,
    atr_take_profit_factor: float = 3.0,
    max_trials: int = 100,
    min_trades: int = 1,
    objective: str = "balanced",
    seed: int = 42,
    enabled_criteria: dict[str, bool] | None = None,
) -> Hyperopt2Result:
    rows: list[dict] = []
    optimize_risk = enabled_criteria is None or enabled_criteria.get("risk_management", True)
    for trial_number, params in enumerate(_candidate_grid(max_trials=max_trials, seed=seed), start=1):
        trial_risk = params.risk_per_trade if optimize_risk else risk_per_trade
        trial_stop = params.atr_stop_factor if optimize_risk else atr_stop_factor
        trial_take_profit = params.atr_take_profit_factor if optimize_risk else atr_take_profit_factor
        indicator_df = add_indicators(price_df, params.indicator_parameters())
        signal_df = generate_signals(indicator_df, params.strategy_parameters(enabled_criteria))
        trades, equity = backtest(
            signal_df,
            initial_capital=initial_capital,
            trading_fee=trading_fee,
            risk_per_trade=trial_risk,
            atr_stop_factor=trial_stop,
            atr_take_profit_factor=trial_take_profit,
        )
        metrics = calculate_metrics(trades, equity, initial_capital)
        values = dict(params.__dict__)
        values.update(risk_per_trade=trial_risk, atr_stop_factor=trial_stop, atr_take_profit_factor=trial_take_profit)
        rows.append(
            {
                "Durchlauf": trial_number,
                **values,
                "Objective": objective_score(metrics, objective, min_trades),
                "Gesamtrendite %": metrics.get("Gesamtrendite %", 0.0),
                "Max. Drawdown %": metrics.get("Max. Drawdown %", 0.0),
                "Abgeschlossene Trades": metrics.get("Abgeschlossene Trades", 0),
                "Trefferquote %": metrics.get("Trefferquote %", 0.0),
                "Endkapital": metrics.get("Endkapital", initial_capital),
            }
        )

    trials = pd.DataFrame(rows).sort_values("Objective", ascending=False).reset_index(drop=True)
    importance = parameter_importance(trials)
    sensitivity = sensitivity_data(trials, importance)
    heatmap = heatmap_data(trials, importance)
    stability = stability_index(trials)
    best = trials.iloc[0]
    buy_hold = buy_and_hold_metrics(price_df, initial_capital)
    oracle = _oracle_metrics(price_df, initial_capital)
    benchmarks = pd.DataFrame(
        [
            {"Vergleich": "Hyperopt 2", "Rendite %": best["Gesamtrendite %"], "Endkapital": best["Endkapital"]},
            {"Vergleich": "Buy & Hold", "Rendite %": buy_hold.get("BuyHold Rendite %", 0.0), "Endkapital": buy_hold.get("BuyHold Endkapital", initial_capital)},
            {"Vergleich": "Oracle", "Rendite %": oracle["Oracle Rendite %"], "Endkapital": oracle["Oracle Endkapital"]},
        ]
    )
    return Hyperopt2Result(
        trials=trials,
        importance=importance,
        sensitivity=sensitivity,
        heatmap=heatmap,
        benchmarks=benchmarks,
        stability_index=stability,
        evaluation=_evaluation(best, benchmarks, stability),
    )


def best_parameters(result: Hyperopt2Result) -> HyperoptParameters | None:
    return best_hyperopt_parameters(result.trials)
