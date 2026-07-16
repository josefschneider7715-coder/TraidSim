from __future__ import annotations

import pandas as pd

from src.backtest import backtest
from src.indicators import add_indicators, sma
from src.scoring import signal_history_payload, strategy_score
from src.strategy import generate_signals
from src.telemetry import apply_enabled_criteria_signals, build_criterion_telemetry


def make_price_frame(periods: int = 260) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": pd.date_range("2020-01-01", periods=periods),
            "Open": range(100, 100 + periods),
            "High": range(102, 102 + periods),
            "Low": range(98, 98 + periods),
            "Close": range(100, 100 + periods),
            "Volume": [1000 + i for i in range(periods)],
        }
    )


def test_sma_uses_rolling_mean() -> None:
    series = pd.Series([1, 2, 3, 4, 5])
    result = sma(series, 3)
    assert pd.isna(result.iloc[1])
    assert result.iloc[-1] == 4


def test_indicators_create_expected_columns() -> None:
    result = add_indicators(make_price_frame())
    expected = [
        "SMA_20",
        "SMA_50",
        "SMA_200",
        "RSI",
        "MACD",
        "MACD_SIGNAL",
        "MACD_HIST",
        "BB_UPPER",
        "BB_MIDDLE",
        "BB_LOWER",
        "ATR",
        "ATR_PCT",
        "VOL_SMA_20",
        "FIB_382",
        "FIB_500",
        "FIB_618",
        "STOCH_K",
        "STOCH_D",
        "ICHIMOKU_CONVERSION",
        "ICHIMOKU_BASE",
        "ICHIMOKU_SPAN_A",
        "ICHIMOKU_SPAN_B",
    ]

    for column in expected:
        assert column in result.columns


def test_rsi_stays_between_zero_and_one_hundred() -> None:
    result = add_indicators(make_price_frame())
    assert result["RSI"].between(0, 100).all()


def test_entry_signal_requires_all_criteria() -> None:
    df = add_indicators(make_price_frame())
    df["Volume"] = df["VOL_SMA_20"].fillna(0) + 100
    result = generate_signals(df)
    latest = result.dropna().iloc[-1]
    assert bool(latest["ENTRY_SIGNAL"])

    df.loc[df.index[-1], "MACD"] = df.loc[df.index[-1], "MACD_SIGNAL"] - 1
    result = generate_signals(df)
    assert not bool(result.iloc[-1]["ENTRY_SIGNAL"])


def test_backtest_creates_equity_curve() -> None:
    df = generate_signals(add_indicators(make_price_frame()))
    trades_df, equity_df = backtest(df)
    assert isinstance(trades_df, pd.DataFrame)
    assert not equity_df.empty
    assert "Equity" in equity_df.columns
    assert not equity_df["Equity"].isna().iloc[-1]


def test_strategy_score_uses_indicator_groups() -> None:
    df = generate_signals(add_indicators(make_price_frame()))
    score = strategy_score(df)
    assert score["max_score"] == 9
    assert len(score["checks"]) == 9
    assert "Fibonacci Unterstuetzung haelt" in score["checks"]
    assert "Stochastik positiv" in score["checks"]
    assert "Ichimoku bullisch" in score["checks"]


def test_signal_history_payload_uses_current_check_names() -> None:
    df = generate_signals(add_indicators(make_price_frame()))
    score = strategy_score(df)
    payload = signal_history_payload("TEST", score)
    assert payload["symbol"] == "TEST"
    assert payload["sma_status"] in {"positiv", "negativ"}
    assert payload["volume_status"] in {"hoch", "normal"}


def test_criterion_telemetry_creates_summary_and_periods() -> None:
    df = generate_signals(add_indicators(make_price_frame()))
    trades_df, _ = backtest(df)
    telemetry = build_criterion_telemetry(df, trades_df)

    assert len(telemetry["summary"]) == 9
    assert not telemetry["events"].empty
    assert not telemetry["weekly"].empty
    assert not telemetry["monthly"].empty
    assert "evaluation_count" in telemetry["summary"].columns
    assert "Rendite_Pct" in telemetry["monthly"].columns
    assert "criterion_relevance_score" in telemetry["ranking"].columns


def test_criterion_telemetry_only_uses_enabled_criteria() -> None:
    df = generate_signals(add_indicators(make_price_frame()))
    enabled = ["trend_filter", "rsi_filter"]
    simulation_df = apply_enabled_criteria_signals(df, enabled)
    trades_df, _ = backtest(simulation_df)
    telemetry = build_criterion_telemetry(simulation_df, trades_df, enabled)

    assert set(telemetry["summary"]["criterion_id"]) == set(enabled)
    assert set(telemetry["events"]["criterion_id"]) == set(enabled)
