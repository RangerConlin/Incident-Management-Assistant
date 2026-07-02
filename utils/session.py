from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
import socket
from typing import Any

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


def _start_api_session(
    *,
    user_id: str,
    username: str | None = None,
    display_name: str | None = None,
    role: str | None = None,
    person_record: int | None = None,
    incident_id: str | None = None,
    mode: str | None = None,
) -> str | None:
    try:
        from utils.api_client import api_client

        payload = {
            "user_id": str(user_id),
            "username": str(username or user_id),
            "display_name": display_name or str(username or user_id),
            "badge_number": str(username or user_id),
            "person_record": person_record,
            "role": role or "",
            "incident_id": incident_id,
            "mode": mode or "",
            "status": "online",
            "device_name": socket.gethostname(),
        }
        doc: dict[str, Any] = api_client.post("/api/auth/sessions", json=payload) or {}
        session_id = doc.get("session_id")
        if session_id:
            AppState.set_active_api_session_id(str(session_id))
            return str(session_id)
    except Exception as exc:
        write_audit("presence.session_start_failed", {"error": str(exc)}, prefer_mission=False)
    return None


def start_session(
    user_id: int | str,
    *,
    username: str | None = None,
    display_name: str | None = None,
    role: str | None = None,
    person_record: int | None = None,
    personnel_id: str | None = None,  # legacy alias, ignored
    incident_id: str | None = None,
    mode: str | None = None,
) -> int | None:
    _start_api_session(
        user_id=str(user_id),
        username=username,
        display_name=display_name,
        role=role,
        person_record=person_record,
        incident_id=incident_id,
        mode=mode,
    )
    try:
        legacy_user_id = int(user_id)
    except (TypeError, ValueError):
        return None

    conn = master_db()
    conn.execute(SCHEMA)
    cur = conn.execute(
        "INSERT INTO user_sessions (user_id, login_utc) VALUES (?, ?)",
        (legacy_user_id, now_utc_iso()),
    )
    session_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    AppState.set_active_session_id(session_id)
    return session_id


def end_session() -> None:
    api_session_id = AppState.get_active_api_session_id()
    if api_session_id:
        try:
            from utils.api_client import api_client

            api_client.post(f"/api/auth/sessions/{api_session_id}/logout")
        except Exception as exc:
            write_audit("presence.session_end_failed", {"error": str(exc)}, prefer_mission=False)
        finally:
            AppState.set_active_api_session_id(None)

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
