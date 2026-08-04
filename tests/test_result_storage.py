from pathlib import Path

import pandas as pd

from src.storage import list_analysis_results, load_analysis_result, save_analysis_result


def test_analysis_results_are_saved_loaded_and_scoped(tmp_path: Path) -> None:
    database = tmp_path / "results.db"
    payload = {"metrics": {"return": 12.5}, "trades": pd.DataFrame({"Profit": [10.0, -2.0]})}
    save_analysis_result("admin", "simulation", "AAPL Test", "AAPL", payload, database)

    entries = list_analysis_results("admin", "simulation", "AAPL", database)
    assert len(entries) == 1
    assert entries[0]["name"] == "AAPL Test"
    loaded = load_analysis_result("admin", entries[0]["id"], "simulation", database)
    assert loaded["metrics"]["return"] == 12.5
    pd.testing.assert_frame_equal(loaded["trades"], payload["trades"])
    assert list_analysis_results("other-user", "simulation", "AAPL", database) == []


def test_saving_same_name_updates_existing_result(tmp_path: Path) -> None:
    database = tmp_path / "results.db"
    save_analysis_result("admin", "hyperopt", "Run 1", "AAPL", {"value": 1}, database)
    save_analysis_result("admin", "hyperopt", "Run 1", "MSFT", {"value": 2}, database)
    entries = list_analysis_results("admin", "hyperopt", db_path=database)
    assert len(entries) == 1
    assert entries[0]["symbol"] == "MSFT"
    assert load_analysis_result("admin", entries[0]["id"], "hyperopt", database)["value"] == 2
