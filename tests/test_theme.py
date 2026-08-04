from pathlib import Path


def test_streamlit_theme_uses_black_background() -> None:
    config = (Path(__file__).parents[1] / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert 'backgroundColor = "#000000"' in config
    assert 'secondaryBackgroundColor = "#141414"' in config
