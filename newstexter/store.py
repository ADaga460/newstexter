"""SQLite persistence: de-duplication of sent stories + inbound chat history.

Lives on a persistent volume so it survives redeploys.
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen (
    url_hash TEXT PRIMARY KEY,
    sent_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    number TEXT NOT NULL,
    role   TEXT NOT NULL,          -- 'user' or 'assistant'
    text   TEXT NOT NULL,
    ts     REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_number_ts ON messages(number, ts);
"""


@contextmanager
def connect(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    """Open a connection, ensuring the schema and parent directory exist."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


# --- De-duplication of sent stories ---

def is_seen(conn: sqlite3.Connection, url_hash: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM seen WHERE url_hash = ?", (url_hash,)
    ).fetchone()
    return row is not None


def is_empty(conn: sqlite3.Connection) -> bool:
    """True if no story has ever been recorded (used to detect a cold start)."""
    return conn.execute("SELECT 1 FROM seen LIMIT 1").fetchone() is None


def mark_seen(conn: sqlite3.Connection, url_hash: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO seen (url_hash, sent_at) VALUES (?, ?)",
        (url_hash, time.time()),
    )


# --- Inbound conversation history ---

def add_message(conn: sqlite3.Connection, number: str, role: str, text: str) -> None:
    conn.execute(
        "INSERT INTO messages (number, role, text, ts) VALUES (?, ?, ?, ?)",
        (number, role, text, time.time()),
    )


def get_history(
    conn: sqlite3.Connection, number: str, limit: int = 6
) -> list[dict[str, str]]:
    """Return the last `limit` turns for a number, oldest first, as Anthropic
    message dicts: [{"role": ..., "content": ...}, ...]."""
    rows = conn.execute(
        "SELECT role, text FROM messages WHERE number = ? ORDER BY ts DESC LIMIT ?",
        (number, limit),
    ).fetchall()
    return [{"role": r["role"], "content": r["text"]} for r in reversed(rows)]
