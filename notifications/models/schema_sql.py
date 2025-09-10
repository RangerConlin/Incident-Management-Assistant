from __future__ import annotations

import sqlite3
from typing import Iterable


MASTER_PREFS_SCHEMA = """
CREATE TABLE IF NOT EXISTS notification_preferences (
    id INTEGER PRIMARY KEY,
    toast_mode TEXT DEFAULT 'auto',
    toast_duration_ms INTEGER DEFAULT 4500
);
"""

MISSION_NOTIFICATIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER,
    title TEXT,
    message TEXT,
    severity TEXT,
    source TEXT,
    entity_type TEXT,
    entity_id TEXT,
    toast_mode TEXT,
    toast_duration_ms INTEGER
);
"""

MASTER_TABLES: Iterable[str] = (
    """
    CREATE TABLE IF NOT EXISTS notification_channels (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS notification_rules (
        id INTEGER PRIMARY KEY,
        channel TEXT,
        rule TEXT
    );
    """,
    MASTER_PREFS_SCHEMA,
)


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, decl: str) -> None:
    cur = conn.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cur]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def ensure_master_schema(conn: sqlite3.Connection) -> None:
    """Create master tables and new columns idempotently."""
    for sql in MASTER_TABLES:
        conn.execute(sql)
    _ensure_column(conn, "notification_preferences", "toast_mode", "TEXT DEFAULT 'auto'")
    _ensure_column(conn, "notification_preferences", "toast_duration_ms", "INTEGER DEFAULT 4500")


def ensure_mission_schema(conn: sqlite3.Connection) -> None:
    """Create mission notifications table and columns idempotently."""
    conn.execute(MISSION_NOTIFICATIONS_SCHEMA)
    _ensure_column(conn, "notifications", "toast_mode", "TEXT")
    _ensure_column(conn, "notifications", "toast_duration_ms", "INTEGER")
