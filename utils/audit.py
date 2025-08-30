"""Simple audit logging helper that includes session metadata.

This writes to `data/master.db` into a table `user_action_log` if present,
creating it on first use. Every record stores the current Incident Number,
User ID, and Role from `utils.state.AppState` so downstream queries can
filter by these values.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from utils.state import AppState

DB_PATH = "data/master.db"


def _ensure_table() -> None:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_action_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT DEFAULT CURRENT_TIMESTAMP,
            incident_number TEXT,
            user_id TEXT,
            role TEXT,
            action TEXT NOT NULL,
            details TEXT
        )
        """
    )
    con.commit()
    con.close()


def log_action(action: str, *, details: str | None = None) -> None:
    """Insert an audit record with the current session metadata.

    Best-effort: any exception is raised to caller if desired; callers may
    also ignore failures as audit should not block workflow.
    """
    _ensure_table()
    inc = AppState.get_active_incident()
    user = AppState.get_active_user_id()
    role = AppState.get_active_user_role()

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO user_action_log (incident_number, user_id, role, action, details) VALUES (?, ?, ?, ?, ?)",
        (str(inc) if inc is not None else None, user, role, action, details),
    )
    con.commit()
    con.close()


__all__ = ["log_action"]

