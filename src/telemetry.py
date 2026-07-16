from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class CriterionDefinition:
    criterion_id: str
    name: str
    group: str


CRITERIA = [
    CriterionDefinition("trend_filter", "SMA Trend positiv", "Trend"),
    CriterionDefinition("rsi_filter", "RSI im Zielbereich", "Momentum"),
    CriterionDefinition("macd_filter", "MACD bullisch", "Momentum"),
    CriterionDefinition("bollinger_filter", "Bollinger Momentum positiv", "Momentum"),
    CriterionDefinition("fibonacci_filter", "Fibonacci Unterstuetzung haelt", "Support"),
    CriterionDefinition("volume_filter", "Volumen bestaetigt", "Liquiditaet"),
    CriterionDefinition("stochastic_filter", "Stochastik positiv", "Momentum"),
    CriterionDefinition("atr_filter", "ATR Volatilitaet handelbar", "Risiko"),
    CriterionDefinition("ichimoku_filter", "Ichimoku bullisch", "Trend"),
]

CORE_CRITERIA = {"trend_filter", "rsi_filter", "macd_filter", "bollinger_filter", "volume_filter"}
MINIMUM_EVALUATIONS = 20
MINIMUM_DECISIVE_EVENTS = 3


def _criterion_checks(df: pd.DataFrame) -> pd.DataFrame:
    result = pd.DataFrame(index=df.index)
    cloud_top = df[["ICHIMOKU_SPAN_A", "ICHIMOKU_SPAN_B"]].max(axis=1)
    result["trend_filter"] = (df["Close"] > df["SMA_50"]) & (df["SMA_50"] > df["SMA_200"])
    result["rsi_filter"] = (df["RSI"] > 40) & (df["RSI"] < 65)
    result["macd_filter"] = (df["MACD"] > df["MACD_SIGNAL"]) & (df["MACD_HIST"] > 0)
    result["bollinger_filter"] = df["Close"] > df["BB_MIDDLE"]
    result["fibonacci_filter"] = df["Close"] > df["FIB_618"]
    result["volume_filter"] = df["Volume"] > df["VOL_SMA_20"]
    result["stochastic_filter"] = (df["STOCH_K"] > 20) & (df["STOCH_K"] < 80) & (df["STOCH_K"] > df["STOCH_D"])
    result["atr_filter"] = (df["ATR_PCT"] >= 1) & (df["ATR_PCT"] <= 8)
    result["ichimoku_filter"] = (df["Close"] > cloud_top) & (df["ICHIMOKU_CONVERSION"] > df["ICHIMOKU_BASE"])
    return result


def selected_criteria(enabled_criteria: list[str] | None = None) -> list[CriterionDefinition]:
    if enabled_criteria is None:
        return CRITERIA
    enabled = set(enabled_criteria)
    return [criterion for criterion in CRITERIA if criterion.criterion_id in enabled]


def apply_enabled_criteria_signals(df: pd.DataFrame, enabled_criteria: list[str] | None = None) -> pd.DataFrame:
    active_criteria = selected_criteria(enabled_criteria)
    result = df.copy()
    if not active_criteria:
        result["ENTRY_SIGNAL"] = False
        return result

    checks = _criterion_checks(result)
    active_ids = [criterion.criterion_id for criterion in active_criteria]
    result["ENTRY_SIGNAL"] = checks[active_ids].all(axis=1)
    return result


def build_criterion_telemetry(
    df: pd.DataFrame,
    trades_df: pd.DataFrame | None = None,
    enabled_criteria: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    clean = df.dropna().copy().reset_index(drop=True)
    active_criteria = selected_criteria(enabled_criteria)
    if clean.empty or not active_criteria:
        empty = pd.DataFrame()
        return {"summary": empty, "weekly": empty, "monthly": empty, "events": empty, "ranking": empty}

    checks = _criterion_checks(clean)
    active_ids = [criterion.criterion_id for criterion in active_criteria]
    clean["criteria_passed"] = checks[active_ids].sum(axis=1)
    clean["is_entry"] = checks[active_ids].all(axis=1)
    clean["is_blocked_candidate"] = (~clean["is_entry"]) & (clean["criteria_passed"] >= max(1, len(active_ids) - 1))

    events = _build_events(clean, checks, active_criteria)
    summary = _aggregate_metrics(events, trades_df)
    weekly = _period_metrics(events, "W")
    monthly = _period_metrics(events, "M")
    ranking = _ranking(summary)

    return {
        "summary": summary,
        "weekly": weekly,
        "monthly": monthly,
        "events": events,
        "ranking": ranking,
    }


def _build_events(df: pd.DataFrame, checks: pd.DataFrame, active_criteria: list[CriterionDefinition]) -> pd.DataFrame:
    rows = []
    for row_index, row in df.iterrows():
        next_window = df.iloc[row_index + 1 : row_index + 6]
        open_price = float(next_window["Open"].iloc[0]) if not next_window.empty else float(row["Close"])
        final_future_close = float(next_window["Close"].iloc[-1]) if not next_window.empty else float(row["Close"])
        max_future_close = float(next_window["Close"].max()) if not next_window.empty else float(row["Close"])
        return_pct = (final_future_close / open_price - 1) * 100 if open_price > 0 else 0.0
        missed_profit_pct = max(0.0, (max_future_close / open_price - 1) * 100) if open_price > 0 else 0.0

        active_core = {criterion.criterion_id for criterion in active_criteria if criterion.criterion_id in CORE_CRITERIA}
        trigger_criteria = active_core or {criterion.criterion_id for criterion in active_criteria}

        for criterion in active_criteria:
            passed = bool(checks.at[row_index, criterion.criterion_id])
            is_trigger_criterion = criterion.criterion_id in trigger_criteria
            role = "none"
            status = "passed" if passed else "failed"
            trigger_count = 0
            support_count = 0
            block_count = 0
            decisive_count = 0
            estimated_return_pct = 0.0
            estimated_missed_profit = 0.0

            if bool(row["is_entry"]):
                role = "trigger" if is_trigger_criterion else "supporting"
                trigger_count = 1 if is_trigger_criterion and passed else 0
                support_count = 1 if passed and not is_trigger_criterion else 0
                decisive_count = 1 if is_trigger_criterion and passed else 0
                estimated_return_pct = return_pct if passed else 0.0
            elif bool(row["is_blocked_candidate"]):
                if not passed:
                    role = "blocking"
                    block_count = 1
                    decisive_count = 1
                    estimated_missed_profit = missed_profit_pct
                elif passed:
                    role = "supporting"
                    support_count = 1

            rows.append(
                {
                    "Date": row["Date"],
                    "criterion_id": criterion.criterion_id,
                    "Kriterium": criterion.name,
                    "Gruppe": criterion.group,
                    "status": status,
                    "role": role,
                    "evaluation_count": 1,
                    "passed_count": 1 if passed else 0,
                    "trigger_count": trigger_count,
                    "block_count": block_count,
                    "support_count": support_count,
                    "decisive_count": decisive_count,
                    "estimated_return_pct": estimated_return_pct,
                    "estimated_missed_profit": estimated_missed_profit,
                }
            )
    return pd.DataFrame(rows)


def _aggregate_metrics(events: pd.DataFrame, trades_df: pd.DataFrame | None) -> pd.DataFrame:
    grouped = (
        events.groupby(["criterion_id", "Kriterium", "Gruppe"], as_index=False)
        .agg(
            evaluation_count=("evaluation_count", "sum"),
            passed_count=("passed_count", "sum"),
            trigger_count=("trigger_count", "sum"),
            block_count=("block_count", "sum"),
            support_count=("support_count", "sum"),
            decisive_count=("decisive_count", "sum"),
            estimated_return_pct=("estimated_return_pct", "sum"),
            estimated_missed_profit_pct=("estimated_missed_profit", "sum"),
        )
        .sort_values(["decisive_count", "trigger_count", "block_count"], ascending=False)
    )

    total_profit = _closed_trade_profit(trades_df)
    trigger_total = max(float(grouped["trigger_count"].sum()), 1.0)
    block_total = max(float(grouped["block_count"].sum()), 1.0)
    grouped["estimated_profit_contribution"] = grouped["trigger_count"] / trigger_total * total_profit
    grouped["estimated_loss_avoidance"] = grouped["block_count"] / block_total * max(-total_profit, 0.0)
    grouped["decision_score"] = (grouped["trigger_count"] + grouped["block_count"] + grouped["decisive_count"]) / grouped[
        "evaluation_count"
    ].clip(lower=1)
    grouped["confidence_score"] = (grouped["evaluation_count"] / MINIMUM_EVALUATIONS).clip(upper=1.0)
    grouped["Bewertung"] = grouped.apply(_rating, axis=1)
    return grouped


def _period_metrics(events: pd.DataFrame, frequency: str) -> pd.DataFrame:
    period_events = events.copy()
    period_events["Periode"] = pd.to_datetime(period_events["Date"]).dt.to_period(frequency).astype(str)
    return (
        period_events.groupby(["Periode", "criterion_id", "Kriterium"], as_index=False)
        .agg(
            Auswertungen=("evaluation_count", "sum"),
            Ausloeser=("trigger_count", "sum"),
            Blockierungen=("block_count", "sum"),
            Unterstuetzend=("support_count", "sum"),
            Entscheidende_Ereignisse=("decisive_count", "sum"),
            Rendite_Pct=("estimated_return_pct", "sum"),
            Verpasste_Gewinne_Pct=("estimated_missed_profit", "sum"),
        )
        .sort_values(["Periode", "Entscheidende_Ereignisse"], ascending=[True, False])
    )


def _ranking(summary: pd.DataFrame) -> pd.DataFrame:
    ranking = summary.copy()
    ranking["profit_score"] = ranking["estimated_profit_contribution"].rank(pct=True)
    ranking["risk_score"] = ranking["estimated_loss_avoidance"].rank(pct=True)
    ranking["stability_score"] = ranking["confidence_score"]
    ranking["criterion_relevance_score"] = (
        0.20 * ranking["decision_score"]
        + 0.30 * ranking["profit_score"]
        + 0.25 * ranking["risk_score"]
        + 0.15 * ranking["stability_score"]
        + 0.10 * ranking["confidence_score"]
    )
    return ranking.sort_values("criterion_relevance_score", ascending=False)


def _closed_trade_profit(trades_df: pd.DataFrame | None) -> float:
    if trades_df is None or trades_df.empty or "Type" not in trades_df.columns or "Profit" not in trades_df.columns:
        return 0.0
    sells = trades_df[trades_df["Type"] == "SELL"]
    return float(sells["Profit"].sum()) if not sells.empty else 0.0


def _rating(row: pd.Series) -> str:
    if row["evaluation_count"] < MINIMUM_EVALUATIONS or row["decisive_count"] < MINIMUM_DECISIVE_EVENTS:
        return "nicht ausreichend beobachtet"
    if row["estimated_profit_contribution"] < 0 and row["estimated_missed_profit_pct"] > 0:
        return "negativ wirkend"
    if row["decision_score"] >= 0.20:
        return "hoch relevant"
    if row["decision_score"] >= 0.10:
        return "mittel relevant"
    if row["decision_score"] > 0:
        return "gering relevant"
    return "unklar"
