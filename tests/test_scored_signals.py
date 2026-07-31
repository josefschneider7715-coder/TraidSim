from __future__ import annotations

import unittest

import pandas as pd

from src.scored_signals import apply_scored_entry_signals


def sample_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": pd.date_range("2025-01-01", periods=3, freq="D"),
            "Open": [100.0, 101.0, 102.0],
            "High": [101.0, 102.0, 103.0],
            "Low": [99.0, 100.0, 101.0],
            "Close": [100.0, 101.0, 102.0],
            "SMA_50": [95.0, 95.0, 95.0],
            "SMA_200": [90.0, 90.0, 90.0],
            "RSI": [50.0, 50.0, 70.0],
            "MACD": [2.0, 2.0, -1.0],
            "MACD_SIGNAL": [1.0, 1.0, 0.0],
            "MACD_HIST": [1.0, 1.0, -1.0],
            "BB_MIDDLE": [98.0, 98.0, 98.0],
            "FIB_618": [97.0, 97.0, 97.0],
            "Volume": [200.0, 50.0, 50.0],
            "VOL_SMA_20": [100.0, 100.0, 100.0],
            "STOCH_K": [60.0, 60.0, 90.0],
            "STOCH_D": [50.0, 50.0, 80.0],
            "ATR_PCT": [2.0, 2.0, 2.0],
            "ICHIMOKU_SPAN_A": [96.0, 96.0, 96.0],
            "ICHIMOKU_SPAN_B": [95.0, 95.0, 95.0],
            "ICHIMOKU_CONVERSION": [99.0, 99.0, 99.0],
            "ICHIMOKU_BASE": [98.0, 98.0, 98.0],
            "ENTRY_SIGNAL": [False, False, False],
            "EXIT_SIGNAL": [False, False, False],
        }
    )


class ScoredSignalTests(unittest.TestCase):
    def test_trend_plus_three_confirmations_creates_entry(self):
        result = apply_scored_entry_signals(
            sample_frame(),
            ["trend_filter", "rsi_filter", "macd_filter", "bollinger_filter", "volume_filter"],
            minimum_confirmations=3,
        )
        self.assertTrue(bool(result.loc[0, "ENTRY_SIGNAL"]))

    def test_two_confirmations_are_not_enough(self):
        frame = sample_frame()
        frame.loc[0, "Volume"] = 50.0
        frame.loc[0, "BB_MIDDLE"] = 105.0
        result = apply_scored_entry_signals(
            frame,
            ["trend_filter", "rsi_filter", "macd_filter", "bollinger_filter", "volume_filter"],
            minimum_confirmations=3,
        )
        self.assertFalse(bool(result.loc[0, "ENTRY_SIGNAL"]))

    def test_active_confirmations_are_capped_when_fewer_than_three(self):
        result = apply_scored_entry_signals(
            sample_frame(),
            ["trend_filter", "rsi_filter", "macd_filter"],
            minimum_confirmations=3,
        )
        self.assertEqual(int(result.loc[0, "ENTRY_REQUIRED_CONFIRMATIONS"]), 2)
        self.assertTrue(bool(result.loc[0, "ENTRY_SIGNAL"]))

    def test_existing_exit_signal_is_preserved(self):
        frame = sample_frame()
        frame.loc[1, "EXIT_SIGNAL"] = True
        result = apply_scored_entry_signals(frame, ["trend_filter", "rsi_filter", "macd_filter"])
        self.assertTrue(bool(result.loc[1, "EXIT_SIGNAL"]))


if __name__ == "__main__":
    unittest.main()
