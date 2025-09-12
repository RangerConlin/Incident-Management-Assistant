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
    # Ensure legacy databases have required columns
    try:
        cur = conn.execute("PRAGMA table_info(audit_logs)")
        col_rows = cur.fetchall()
        cols = [row[1] for row in col_rows]

        # Add columns used by this module if missing. We keep them nullable to
        # avoid issues altering existing tables with data.
        needed_columns = {
            "ts_utc": "TEXT",
            "user_id": "INTEGER",
            "action": "TEXT",
            "detail": "TEXT",
            "incident_number": "TEXT",
        }

        for col_name, col_type in needed_columns.items():
            if col_name not in cols:
                conn.execute(f"ALTER TABLE audit_logs ADD COLUMN {col_name} {col_type}")

        # If legacy objective bridge created audit_logs with NOT NULL taskid
        # it will block our inserts that don't provide taskid. Relax it by
        # rebuilding the table with a superset schema where taskid is nullable.
        taskid_notnull = False
        for r in col_rows:
            if r[1] == "taskid":  # row format: cid, name, type, notnull, dflt_value, pk
                taskid_notnull = bool(r[3])
                break
        if taskid_notnull:
            # Build a new table with the union of known columns and relaxed constraints
            union_columns = [
                ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
                ("ts_utc", "TEXT"),
                ("user_id", "INTEGER"),
                ("action", "TEXT"),
                ("detail", "TEXT"),
                ("incident_number", "TEXT"),
                ("taskid", "INTEGER"),  # now nullable
                ("field_changed", "TEXT"),
                ("old_value", "TEXT"),
                ("new_value", "TEXT"),
                ("changed_by", "INTEGER"),
                ("timestamp", "TEXT"),
            ]
            create_sql = (
                "CREATE TABLE IF NOT EXISTS audit_logs_mig (" + 
                ", ".join([f"{n} {t}" for n, t in union_columns]) + ")"
            )
            conn.execute(create_sql)

            # Compose column list and SELECT with fallback NULLs for missing columns
            existing_cols = set(cols)
            names = [n for n, _ in union_columns]
            select_items = [
                (n if n in existing_cols else f"NULL AS {n}") for n in names
            ]
            # id is PK; when copying we should preserve if present, else let autoinc assign
            if "id" not in existing_cols:
                # Replace first select item to NULL for id
                select_items[0] = "NULL AS id"

            insert_sql = (
                "INSERT INTO audit_logs_mig (" + ",".join(names) + ") "
                "SELECT " + ",".join(select_items) + " FROM audit_logs"
            )
            conn.execute(insert_sql)
            conn.execute("DROP TABLE audit_logs")
            conn.execute("ALTER TABLE audit_logs_mig RENAME TO audit_logs")
            # Refresh schema info for subsequent steps
            col_rows = list(conn.execute("PRAGMA table_info(audit_logs)"))
            cols = [row[1] for row in col_rows]

        # Best-effort backfill for timestamps if legacy columns exist
        if "ts_utc" in needed_columns and "ts_utc" in (row[1] for row in conn.execute("PRAGMA table_info(audit_logs)")):
            # Refresh col list and backfill from common legacy names
            cols = [row[1] for row in conn.execute("PRAGMA table_info(audit_logs)").fetchall()]
            if "ts_utc" in cols:
                if "ts" in cols:
                    conn.execute(
                        "UPDATE audit_logs SET ts_utc = ts WHERE ts_utc IS NULL AND ts IS NOT NULL"
                    )
                if "timestamp" in cols:
                    conn.execute(
                        "UPDATE audit_logs SET ts_utc = timestamp WHERE ts_utc IS NULL AND timestamp IS NOT NULL"
                    )
        conn.commit()
    except Exception:
        # If anything goes wrong, we proceed without blocking writes; future
        # inserts specify column lists explicitly, so extra legacy columns are fine.
        pass
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
