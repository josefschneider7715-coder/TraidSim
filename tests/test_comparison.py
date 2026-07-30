from __future__ import annotations

import unittest

import pandas as pd

from src.comparison import (
    align_equity_curves,
    run_buy_and_hold_benchmark,
    run_oracle_benchmark,
    run_strategy_benchmark,
)


def market(close_values: list[float]) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=len(close_values), freq="D")
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": close_values,
            "High": [value * 1.01 for value in close_values],
            "Low": [value * 0.99 for value in close_values],
            "Close": close_values,
            "ATR": [1.0] * len(close_values),
            "ENTRY_SIGNAL": [False] * len(close_values),
            "EXIT_SIGNAL": [False] * len(close_values),
        }
    )


class ComparisonTests(unittest.TestCase):
    def test_oracle_stays_in_cash_in_falling_market(self):
        result = run_oracle_benchmark(market([100, 90, 80, 70]), 10_000, 0.001)
        self.assertAlmostEqual(result.metrics["Endkapital"], 10_000, places=6)
        self.assertEqual(result.metrics["Abgeschlossene Trades"], 0)

    def test_oracle_buys_and_sells_rising_market(self):
        result = run_oracle_benchmark(market([100, 110, 120]), 10_000, 0.001)
        self.assertGreater(result.metrics["Endkapital"], 10_000)
        self.assertEqual(result.metrics["Abgeschlossene Trades"], 1)
        sells = result.trades[result.trades["Type"] == "SELL"]
        self.assertTrue((sells["Profit"] > 0).all())

    def test_high_fees_filter_small_move(self):
        result = run_oracle_benchmark(market([100, 100.5, 100.2]), 10_000, 0.01)
        self.assertEqual(result.metrics["Abgeschlossene Trades"], 0)

    def test_buy_hold_charges_entry_and_exit_fee(self):
        result = run_buy_and_hold_benchmark(market([100, 100]), 10_000, 0.001)
        self.assertLess(result.metrics["Endkapital"], 10_000)
        self.assertGreater(result.metrics["Gebuehren gesamt"], 0)

    def test_strategy_forces_final_liquidation(self):
        df = market([100, 101, 102])
        df.loc[0, "ENTRY_SIGNAL"] = True
        result = run_strategy_benchmark(df, 10_000, trading_fee=0.001, position_mode="full_capital")
        self.assertEqual(result.trades.iloc[-1]["Reason"], "Ende Zeitfenster")
        self.assertEqual(result.equity.iloc[-1]["Position_Value"], 0)

    def test_curves_are_aligned(self):
        df = market([100, 102, 101, 104])
        strategy = run_strategy_benchmark(df)
        buy_hold = run_buy_and_hold_benchmark(df)
        oracle = run_oracle_benchmark(df)
        aligned = align_equity_curves(strategy, buy_hold, oracle)
        self.assertEqual(len(aligned), len(df))
        self.assertFalse(aligned[["Strategie", "Buy and Hold", "Oracle"]].isna().any().any())


if __name__ == "__main__":
    unittest.main()
