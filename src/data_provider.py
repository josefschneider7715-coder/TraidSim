from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd


YFINANCE_CACHE_DIR = Path(__file__).resolve().parents[1] / ".yfinance_cache"
BINANCE_BASE_URLS = [
    "https://api.binance.com/api/v3/klines",
    "https://api.binance.us/api/v3/klines",
]
CRYPTO_BASES = {
    "BTC",
    "ETH",
    "SOL",
    "BNB",
    "XRP",
    "ADA",
    "DOGE",
    "AVAX",
    "DOT",
    "LINK",
    "MATIC",
    "LTC",
    "BCH",
    "UNI",
    "ATOM",
    "TRX",
    "TON",
    "NEAR",
    "APT",
    "ARB",
    "OP",
    "INJ",
}
BINANCE_INTERVALS = {"1d": "1d", "1wk": "1w", "1mo": "1M"}
PERIOD_OFFSETS = {
    "6mo": pd.DateOffset(months=6),
    "1y": pd.DateOffset(years=1),
    "2y": pd.DateOffset(years=2),
    "5y": pd.DateOffset(years=5),
    "10y": pd.DateOffset(years=10),
    "max": pd.DateOffset(years=10),
}


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


def crypto_usdt_symbol(symbol: str) -> str | None:
    normalized = symbol.strip().upper().replace("/", "-").replace("_", "-")
    if normalized.endswith("-USDT"):
        base = normalized.removesuffix("-USDT")
        return f"{base}USDT" if base in CRYPTO_BASES else None
    if normalized.endswith("-USD"):
        base = normalized.removesuffix("-USD")
        return f"{base}USDT" if base in CRYPTO_BASES else None
    if normalized.endswith("USDT"):
        base = normalized.removesuffix("USDT")
        return normalized if base in CRYPTO_BASES else None
    return None


class BinanceUSDTDataProvider(MarketDataProvider):
    def get_history(self, symbol: str, period: str = "5y", interval: str = "1d") -> pd.DataFrame:
        binance_symbol = crypto_usdt_symbol(symbol)
        if binance_symbol is None:
            raise ValueError(f"{symbol} ist kein unterstuetztes USDT-Kryptopaar.")
        if interval not in BINANCE_INTERVALS:
            raise ValueError("Binance-Kryptodaten unterstuetzen aktuell 1d, 1wk und 1mo.")

        end_time = pd.Timestamp.now(tz="UTC")
        start_time = end_time - PERIOD_OFFSETS.get(period, PERIOD_OFFSETS["5y"])
        end_ms = int(end_time.timestamp() * 1000)
        last_error = None

        for base_url in BINANCE_BASE_URLS:
            rows = []
            next_start_ms = int(start_time.timestamp() * 1000)
            try:
                while next_start_ms < end_ms:
                    query = urlencode(
                        {
                            "symbol": binance_symbol,
                            "interval": BINANCE_INTERVALS[interval],
                            "startTime": next_start_ms,
                            "endTime": end_ms,
                            "limit": 1000,
                        }
                    )
                    with urlopen(f"{base_url}?{query}", timeout=20) as response:
                        chunk = pd.read_json(response)

                    if chunk.empty:
                        break

                    rows.append(chunk)
                    last_open_time = int(chunk.iloc[-1, 0])
                    next_start_ms = last_open_time + 1
                    if len(chunk) < 1000:
                        break
            except Exception as exc:
                last_error = exc
                continue

            if rows:
                break
        else:
            error_text = f" Letzter Fehler: {last_error}" if last_error else ""
            raise ValueError(f"Keine Binance-USDT-Kursdaten fuer {binance_symbol} erhalten.{error_text}")

        raw = pd.concat(rows, ignore_index=True)
        raw = raw.iloc[:, [0, 1, 2, 3, 4, 5]]
        raw.columns = ["Date", "Open", "High", "Low", "Close", "Volume"]
        raw["Date"] = pd.to_datetime(raw["Date"], unit="ms")
        for column in ["Open", "High", "Low", "Close", "Volume"]:
            raw[column] = pd.to_numeric(raw[column], errors="coerce")

        required = ["Date", "Open", "High", "Low", "Close", "Volume"]
        return raw[required].dropna().drop_duplicates("Date").sort_values("Date").reset_index(drop=True)


def download_data(symbol: str, period: str = "5y", interval: str = "1d") -> pd.DataFrame:
    if crypto_usdt_symbol(symbol):
        return BinanceUSDTDataProvider().get_history(symbol, period, interval)
    return YFinanceDataProvider().get_history(symbol, period, interval)
