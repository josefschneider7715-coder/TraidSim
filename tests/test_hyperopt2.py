from __future__ import annotations

import pandas as pd

from src.hyperopt2 import (
    OBJECTIVES,
    objective_score,
    recommended_criteria,
    result_from_payload,
    result_to_payload,
    run_hyperopt2,
)


def make_price_frame(periods: int = 260) -> pd.DataFrame:
    close = pd.Series([100.0 + index * 0.25 + (index % 7) * 0.2 for index in range(periods)])
    return pd.DataFrame(
        {
            "Date": pd.date_range("2022-01-01", periods=periods),
            "Open": close - 0.1,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": [1000 + (index % 11) * 50 for index in range(periods)],
        }
    )


def test_all_hyperopt2_objectives_return_finite_scores() -> None:
    metrics = {
        "Gesamtrendite %": 12.0,
        "Max. Drawdown %": -5.0,
        "Trefferquote %": 60.0,
        "Abgeschlossene Trades": 4,
    }
    for objective in OBJECTIVES:
        assert objective_score(metrics, objective, min_trades=1) > -1_000_000


def test_hyperopt2_builds_professional_analysis_artifacts() -> None:
    result = run_hyperopt2(
        make_price_frame(),
        max_trials=5,
        min_trades=0,
        enabled_criteria={"trend": True, "rsi": False, "macd": False, "bollinger": False, "volume": False},
    )
    assert len(result.trials) == 5
    assert not result.importance.empty
    assert not result.sensitivity.empty
    assert len(result.benchmarks) == 3
    assert set(result.benchmarks["Vergleich"]) == {"Hyperopt", "Buy & Hold", "Oracle"}
    assert 0 <= result.stability_index <= 100
    assert "Stabilitaetsindex" in result.evaluation
    recommendation = recommended_criteria(result)
    assert recommendation["trend"] is True
    assert not any(value for key, value in recommendation.items() if key != "trend")


def test_hyperopt2_result_has_reload_safe_storage_roundtrip() -> None:
    result = run_hyperopt2(make_price_frame(), max_trials=3, min_trades=0)
    restored = result_from_payload(result_to_payload(result))
    pd.testing.assert_frame_equal(restored.trials, result.trials)
    pd.testing.assert_frame_equal(restored.importance, result.importance)
    assert restored.stability_index == result.stability_index
    assert restored.evaluation == result.evaluation
