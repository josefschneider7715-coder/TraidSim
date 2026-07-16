from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

import pandas as pd


DB_PATH = Path(__file__).resolve().parents[1] / "app_data.db"


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS watchlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                symbols TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS signal_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                date TEXT NOT NULL,
                close REAL NOT NULL,
                signal TEXT NOT NULL,
                score INTEGER NOT NULL,
                rsi REAL NOT NULL,
                macd_status TEXT NOT NULL,
                sma_status TEXT NOT NULL,
                volume_status TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, date)
            );
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                date TEXT NOT NULL,
                signal TEXT NOT NULL,
                score INTEGER NOT NULL,
                close REAL NOT NULL,
                is_read INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, date, signal)
            );
            """
        )


def list_watchlists() -> list[dict]:
    init_db()
    with get_connection() as connection:
        rows = connection.execute("SELECT id, name, symbols, updated_at FROM watchlists ORDER BY name").fetchall()
    return [dict(row) for row in rows]


def save_watchlist(name: str, symbols: Iterable[str]) -> None:
    clean_name = name.strip()
    clean_symbols = ",".join(symbol.strip().upper() for symbol in symbols if symbol.strip())

    if not clean_name:
        raise ValueError("Watchlist-Name fehlt.")
    if not clean_symbols:
        raise ValueError("Watchlist enthaelt keine Symbole.")

    init_db()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO watchlists(name, symbols)
            VALUES(?, ?)
            ON CONFLICT(name) DO UPDATE SET
                symbols = excluded.symbols,
                updated_at = CURRENT_TIMESTAMP
            """,
            (clean_name, clean_symbols),
        )


def save_signal_history(payload: dict) -> None:
    init_db()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO signal_history(symbol, date, close, signal, score, rsi, macd_status, sma_status, volume_status)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, date) DO UPDATE SET
                close = excluded.close,
                signal = excluded.signal,
                score = excluded.score,
                rsi = excluded.rsi,
                macd_status = excluded.macd_status,
                sma_status = excluded.sma_status,
                volume_status = excluded.volume_status
            """,
            (
                payload["symbol"],
                str(pd.Timestamp(payload["date"]).date()),
                payload["close"],
                payload["signal"],
                payload["score"],
                payload["rsi"],
                payload["macd_status"],
                payload["sma_status"],
                payload["volume_status"],
            ),
        )


def create_alert_if_buy(payload: dict) -> None:
    if payload["signal"] != "KAUF":
        return

    init_db()
    with get_connection() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO alerts(symbol, date, signal, score, close) VALUES(?, ?, ?, ?, ?)",
            (
                payload["symbol"],
                str(pd.Timestamp(payload["date"]).date()),
                payload["signal"],
                payload["score"],
                payload["close"],
            ),
        )


def recent_alerts(limit: int = 20) -> list[dict]:
    init_db()
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, symbol, date, signal, score, close, is_read, created_at
            FROM alerts
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def recent_signal_history(limit: int = 100) -> list[dict]:
    init_db()
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT symbol, date, close, signal, score, rsi, macd_status, sma_status, volume_status
            FROM signal_history
            ORDER BY date DESC, symbol ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]
