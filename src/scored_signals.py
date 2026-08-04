from __future__ import annotations

import pandas as pd

from src.strategy import StrategyParameters
from src.telemetry import _criterion_checks, selected_criteria


DEFAULT_MIN_CONFIRMATIONS = 3


def apply_scored_entry_signals(
    df: pd.DataFrame,
    enabled_criteria: list[str] | None = None,
    minimum_confirmations: int = DEFAULT_MIN_CONFIRMATIONS,
    params: StrategyParameters | None = None,
) -> pd.DataFrame:
    """Erzeugt robustere Einstiegssignale statt einer Alles-oder-nichts-Regel.

    Regeln:
    - Der SMA-Trendfilter ist Pflicht, sofern er aktiviert ist.
    - Von allen weiteren aktivierten Kriterien müssen mindestens drei erfüllt
      sein. Sind weniger als drei Bestätiger aktiv, müssen alle aktiven
      Bestätiger erfüllt sein.
    - Vorhandene EXIT_SIGNAL-Regeln bleiben unverändert.
    """
    result = df.copy()
    active = selected_criteria(enabled_criteria)
    active_ids = [criterion.criterion_id for criterion in active]

    if not active_ids:
        result["ENTRY_SIGNAL"] = False
        result["ENTRY_CONFIRMATIONS"] = 0
        result["ENTRY_REQUIRED_CONFIRMATIONS"] = 0
        return result

    checks = _criterion_checks(result, params).fillna(False)
    trend_required = "trend_filter" in active_ids
    confirmation_ids = [criterion_id for criterion_id in active_ids if criterion_id != "trend_filter"]

    if confirmation_ids:
        confirmation_count = checks[confirmation_ids].sum(axis=1).astype(int)
        required_confirmations = min(max(1, int(minimum_confirmations)), len(confirmation_ids))
        confirmation_ok = confirmation_count >= required_confirmations
    else:
        confirmation_count = pd.Series(0, index=result.index, dtype=int)
        required_confirmations = 0
        confirmation_ok = pd.Series(True, index=result.index)

    trend_ok = checks["trend_filter"] if trend_required else pd.Series(True, index=result.index)
    result["ENTRY_SIGNAL"] = (trend_ok & confirmation_ok).fillna(False)
    result["ENTRY_CONFIRMATIONS"] = confirmation_count
    result["ENTRY_REQUIRED_CONFIRMATIONS"] = required_confirmations
    result["ENTRY_TREND_REQUIRED"] = trend_required
    return result
