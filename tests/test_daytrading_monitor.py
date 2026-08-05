import pandas as pd

from src.daytrading_monitor import simulate_current_day


def test_day_profit_curve_is_created() -> None:
    rows = 260
    frame = pd.DataFrame({
        "Date": pd.date_range("2026-08-03 09:00", periods=rows, freq="5min"),
        "Open": range(100, 100 + rows), "High": range(102, 102 + rows),
        "Low": range(98, 98 + rows), "Close": range(100, 100 + rows),
        "Volume": [1000 + index for index in range(rows)],
    })
    result = simulate_current_day(frame, 10_000.0, 0.001)
    assert not result.empty
    assert {"Equity", "Gewinn", "Position"}.issubset(result.columns)
