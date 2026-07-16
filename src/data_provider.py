from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd


YFINANCE_CACHE_DIR = Path(__file__).resolve().parents[1] / ".yfinance_cache"


class MarketDataProvider(ABC):
    @abstractmethod
    def get_history(self, symbol: str, period: str, interval: str) -> pd.DataFrame:
        """Return historical OHLCV data for a symbol."""


class YFinanceDataProvider(MarketDataProvider):
    def get_history(self, symbol: str, period: str = "5y", interval: str = "1d") -> pd.DataFrame:
        try:
            import yfinance as yf
        except ImportError as exc:
            raise ImportError("yfinance fehlt. Installation: pip install yfinance") from exc

        YFINANCE_CACHE_DIR.mkdir(exist_ok=True)
        yf.cache.set_cache_location(str(YFINANCE_CACHE_DIR))
        yf.set_tz_cache_location(str(YFINANCE_CACHE_DIR))

        df = yf.download(symbol, period=period, interval=interval, auto_adjust=True, progress=False, threads=True)

        if df.empty:
            raise ValueError(f"Keine Kursdaten fuer {symbol} erhalten.")

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.reset_index()

        if "Datetime" in df.columns and "Date" not in df.columns:
            df = df.rename(columns={"Datetime": "Date"})

        required = ["Date", "Open", "High", "Low", "Close", "Volume"]
        missing = [column for column in required if column not in df.columns]

        if missing:
            raise ValueError(f"Fehlende Spalten: {missing}")

        return df[required].dropna().sort_values("Date").reset_index(drop=True)


def download_data(symbol: str, period: str = "5y", interval: str = "1d") -> pd.DataFrame:
    return YFinanceDataProvider().get_history(symbol, period, interval)
