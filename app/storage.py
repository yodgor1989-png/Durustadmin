"""Kichik SQLite xotira: bir xil ogohlantirish takror yuborilmasin."""

from __future__ import annotations

import datetime as dt
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "bot_state.db"


def init() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notified (
                page_id TEXT NOT NULL,
                kind    TEXT NOT NULL,
                day     TEXT NOT NULL,
                PRIMARY KEY (page_id, kind, day)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                day        TEXT PRIMARY KEY,
                total      INTEGER,
                bad        INTEGER,
                overdue    INTEGER,
                created_at TEXT
            )
            """
        )


def already_notified(page_id: str, kind: str, day: dt.date) -> bool:
    """Shu zadacha bo'yicha bugun allaqachon xabar berilganmi."""
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT 1 FROM notified WHERE page_id=? AND kind=? AND day=?",
            (page_id, kind, day.isoformat()),
        ).fetchone()
    return row is not None


def mark_notified(page_id: str, kind: str, day: dt.date) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO notified (page_id, kind, day) VALUES (?, ?, ?)",
            (page_id, kind, day.isoformat()),
        )


def save_report(day: dt.date, total: int, bad: int, overdue: int) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO reports (day, total, bad, overdue, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (day.isoformat(), total, bad, overdue, dt.datetime.now().isoformat()),
        )


def cleanup(older_than_days: int = 60) -> None:
    """Eski yozuvlarni tozalash."""
    cutoff = (dt.date.today() - dt.timedelta(days=older_than_days)).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM notified WHERE day < ?", (cutoff,))
