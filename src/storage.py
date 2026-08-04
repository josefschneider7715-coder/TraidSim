from __future__ import annotations

import sqlite3
import pickle
from pathlib import Path
from typing import Iterable

import pandas as pd


DB_PATH = Path(__file__).resolve().parents[1] / "app_data.db"


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(db_path: Path = DB_PATH) -> None:
    with get_connection(db_path) as connection:
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
            CREATE TABLE IF NOT EXISTS analysis_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                result_type TEXT NOT NULL,
                name TEXT NOT NULL,
                symbol TEXT NOT NULL,
                payload BLOB NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(username, result_type, name)
            );
            """
        )


def save_analysis_result(
    username: str,
    result_type: str,
    name: str,
    symbol: str,
    payload: object,
    db_path: Path = DB_PATH,
) -> None:
    clean_user = username.strip() or "default"
    clean_name = name.strip()
    clean_symbol = symbol.strip().upper()
    if result_type not in {"hyperopt", "simulation"}:
        raise ValueError("Unbekannter Ergebnistyp.")
    if not clean_name:
        raise ValueError("Name für das Ergebnis fehlt.")
    if not clean_symbol:
        raise ValueError("Symbol für das Ergebnis fehlt.")
    encoded = pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)
    init_db(db_path)
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO analysis_results(username, result_type, name, symbol, payload)
            VALUES(?, ?, ?, ?, ?)
            ON CONFLICT(username, result_type, name) DO UPDATE SET
                symbol = excluded.symbol,
                payload = excluded.payload,
                updated_at = CURRENT_TIMESTAMP
            """,
            (clean_user, result_type, clean_name, clean_symbol, sqlite3.Binary(encoded)),
        )


def list_analysis_results(username: str, result_type: str, symbol: str | None = None, db_path: Path = DB_PATH) -> list[dict]:
    init_db(db_path)
    query = "SELECT id, name, symbol, created_at, updated_at FROM analysis_results WHERE username = ? AND result_type = ?"
    values: list[object] = [username.strip() or "default", result_type]
    if symbol:
        query += " AND symbol = ?"
        values.append(symbol.strip().upper())
    query += " ORDER BY updated_at DESC, name"
    with get_connection(db_path) as connection:
        rows = connection.execute(query, values).fetchall()
    return [dict(row) for row in rows]


def load_analysis_result(username: str, result_id: int, result_type: str, db_path: Path = DB_PATH) -> object:
    init_db(db_path)
    with get_connection(db_path) as connection:
        row = connection.execute(
            "SELECT payload FROM analysis_results WHERE id = ? AND username = ? AND result_type = ?",
            (int(result_id), username.strip() or "default", result_type),
        ).fetchone()
    if row is None:
        raise ValueError("Gespeichertes Ergebnis wurde nicht gefunden.")
    return pickle.loads(bytes(row["payload"]))


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
