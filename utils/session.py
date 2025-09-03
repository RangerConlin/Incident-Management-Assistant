from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from utils.context import master_db
from utils.state import AppState
from utils.audit import now_utc_iso, write_audit

SCHEMA = """
CREATE TABLE IF NOT EXISTS user_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  login_utc TEXT NOT NULL,
  logout_utc TEXT
)
"""


def start_session(user_id: int) -> int:
    conn = master_db()
    conn.execute(SCHEMA)
    cur = conn.execute(
        "INSERT INTO user_sessions (user_id, login_utc) VALUES (?, ?)",
        (int(user_id), now_utc_iso()),
    )
    session_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    AppState.set_active_session_id(session_id)
    return session_id


def end_session() -> None:
    session_id = AppState.get_active_session_id()
    if not session_id:
        return
    conn = master_db()
    conn.execute(SCHEMA)
    conn.execute(
        "UPDATE user_sessions SET logout_utc = ? WHERE id = ? AND logout_utc IS NULL",
        (now_utc_iso(), int(session_id)),
    )
    conn.commit()
    conn.close()
    AppState.set_active_session_id(None)


__all__ = ["start_session", "end_session"]
