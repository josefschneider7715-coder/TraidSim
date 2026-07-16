from __future__ import annotations

import pandas as pd

from src.strategy import evaluate_latest


def strategy_score(df: pd.DataFrame) -> dict:
    return evaluate_latest(df)


def signal_history_payload(symbol: str, score: dict) -> dict:
    checks = score["checks"]
    return {
        "symbol": symbol,
        "date": score["date"],
        "close": score["close"],
        "signal": score["signal"],
        "score": score["score"],
        "rsi": score["rsi"],
        "macd_status": "bullisch" if score["macd"] > score["macd_signal"] else "baerisch",
        "sma_status": "positiv" if checks.get("SMA Trend positiv", False) else "negativ",
        "volume_status": "hoch" if checks.get("Volumen bestaetigt", False) else "normal",
    }
