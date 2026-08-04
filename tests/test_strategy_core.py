from __future__ import annotations

import pandas as pd

from src.backtest import backtest
from src.data_provider import crypto_usdt_symbol
from src.hyperopt import HyperoptParameters
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


def test_crypto_symbols_are_mapped_to_usdt_pairs() -> None:
    assert crypto_usdt_symbol("BTC-USD") == "BTCUSDT"
    assert crypto_usdt_symbol("ETH-USDT") == "ETHUSDT"
    assert crypto_usdt_symbol("SOLUSDT") == "SOLUSDT"
    assert crypto_usdt_symbol("AAPL") is None


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


def test_simulation_and_hyperopt_use_identical_entry_logic() -> None:
    enabled_hyperopt = {
        "trend": False,
        "rsi": True,
        "macd": True,
        "bollinger": True,
        "fibonacci": True,
        "volume": True,
        "stoch": False,
        "atr": True,
        "ichimoku": True,
    }
    enabled_simulation = [
        "rsi_filter", "macd_filter", "bollinger_filter", "fibonacci_filter",
        "volume_filter", "atr_filter", "ichimoku_filter",
    ]
    params = HyperoptParameters(
        sma_trend_period=50,
        rsi_period=14, rsi_min=35, rsi_max=70, exit_rsi_max=75,
        macd_fast=16, macd_slow=35, macd_signal=7,
        bb_period=20, bb_std=1.8, fib_lookback=90,
        volume_period=20, volume_factor=1.0,
        stoch_period=14, stoch_signal=3, stoch_min=20, stoch_max=80,
        atr_period=21, atr_min_pct=1.5, atr_max_pct=8.0,
        ichimoku_tenkan=12, ichimoku_kijun=22, ichimoku_senkou_b=44,
        risk_per_trade=0.02, atr_stop_factor=1.5, atr_take_profit_factor=5.0,
    )
    indicator_df = add_indicators(make_price_frame(), params.indicator_parameters())
    hyperopt_df = generate_signals(indicator_df, params.strategy_parameters(enabled_hyperopt))
    simulation_df = apply_enabled_criteria_signals(
        hyperopt_df,
        enabled_simulation,
        params=params.strategy_parameters(enabled_hyperopt),
    )
    pd.testing.assert_series_equal(
        hyperopt_df["ENTRY_SIGNAL"], simulation_df["ENTRY_SIGNAL"], check_names=False
    )
