from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Callable, Dict, Any

from utils.context import master_db, require_incident_db
from utils.state import AppState


SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc TEXT NOT NULL,
  user_id INTEGER,
  action TEXT NOT NULL,
  detail TEXT,
  incident_number TEXT
)
"""


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _get_conn(prefer_mission: bool) -> sqlite3.Connection:
    if prefer_mission:
        try:
            conn = require_incident_db()
        except Exception:
            conn = master_db()
    else:
        conn = master_db()
    conn.execute(SCHEMA)
    return conn


def write_audit(action: str, detail: Dict[str, Any] | None = None, *, prefer_mission: bool = True) -> None:
    conn = _get_conn(prefer_mission)
    user = AppState.get_active_user_id()
    try:
        user_id = int(user) if user is not None else None
    except Exception:
        user_id = None
    incident = AppState.get_active_incident()
    payload = json.dumps(detail, ensure_ascii=False) if detail is not None else None
    conn.execute(
        "INSERT INTO audit_logs (ts_utc, user_id, action, detail, incident_number) VALUES (?, ?, ?, ?, ?)",
        (now_utc_iso(), user_id, action, payload, incident),
    )
    conn.commit()
    conn.close()


def audit_action(action: str, *, prefer_mission: bool = True) -> Callable:
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
            except Exception as e:  # pragma: no cover - passthrough
                write_audit(action, {"result": "error", "error": repr(e)}, prefer_mission=prefer_mission)
                raise
            else:
                write_audit(action, {"result": "ok"}, prefer_mission=prefer_mission)
                return result
        return wrapper
    return decorator


def fetch_last_audit_rows(limit: int = 10) -> list[sqlite3.Row]:
    try:
        conn = require_incident_db()
    except Exception:
        conn = master_db()
    conn.execute(SCHEMA)
    cur = conn.execute(
        "SELECT id, ts_utc, user_id, action, detail, incident_number FROM audit_logs ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = cur.fetchall() or []
    conn.close()
    return rows


__all__ = ["write_audit", "audit_action", "now_utc_iso", "fetch_last_audit_rows"]
