from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List, Optional

from utils import incident_context

from .models import HastyTaskRecord, ReflexActionRecord

MIGRATION_PATH = Path(__file__).resolve().parent / "data" / "migrations" / "0001_init.sql"


def _resolve_db_path(incident_id: str | None = None) -> Path:
    if incident_id:
        base = Path(os.environ.get("CHECKIN_DATA_DIR", "data")) / "incidents"
        base.mkdir(parents=True, exist_ok=True)
        return base / f"{incident_id}.db"
    return Path(incident_context.get_active_incident_db_path())


def _ensure_schema(conn: sqlite3.Connection) -> None:
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    conn.executescript(sql)


@contextmanager
def connect(incident_id: str | None = None) -> Iterator[sqlite3.Connection]:
    path = _resolve_db_path(incident_id)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        _ensure_schema(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_hasty_task(record: HastyTaskRecord) -> HastyTaskRecord:
    payload = asdict(record)
    payload["incident_id"] = payload.get("incident_id") or _require_incident_id()
    payload["created_at"] = payload.get("created_at") or _utcnow()
    with connect(payload["incident_id"]) as conn:
        cur = conn.execute(
            """
            INSERT INTO initial_hasty_tasks (
                incident_id, area, priority, notes, operations_task_id, logistics_request_id, created_at
            ) VALUES (
                :incident_id, :area, :priority, :notes, :operations_task_id, :logistics_request_id, :created_at
            )
            """,
            payload,
        )
        new_id = int(cur.lastrowid)
        return record.replace(
            id=new_id,
            incident_id=payload["incident_id"],
            created_at=payload["created_at"],
        )


def list_hasty_tasks(incident_id: str | None = None) -> List[HastyTaskRecord]:
    with connect(incident_id) as conn:
        rows = conn.execute(
            """
            SELECT id, incident_id, area, priority, notes, operations_task_id, logistics_request_id, created_at
            FROM initial_hasty_tasks
            ORDER BY created_at DESC
            """
        ).fetchall()
        return [HastyTaskRecord.from_row(dict(row)) for row in rows]


def update_hasty_task_task_id(record_id: int, *, operations_task_id: int, incident_id: str | None = None) -> None:
    with connect(incident_id) as conn:
        conn.execute(
            "UPDATE initial_hasty_tasks SET operations_task_id = ? WHERE id = ?",
            (operations_task_id, record_id),
        )


def add_reflex_action(record: ReflexActionRecord) -> ReflexActionRecord:
    payload = asdict(record)
    payload["incident_id"] = payload.get("incident_id") or _require_incident_id()
    payload["created_at"] = payload.get("created_at") or _utcnow()
    with connect(payload["incident_id"]) as conn:
        cur = conn.execute(
            """
            INSERT INTO initial_reflex_actions (
                incident_id, trigger, action, communications_alert_id, created_at
            ) VALUES (:incident_id, :trigger, :action, :communications_alert_id, :created_at)
            """,
            payload,
        )
        new_id = int(cur.lastrowid)
        return record.replace(
            id=new_id,
            incident_id=payload["incident_id"],
            created_at=payload["created_at"],
        )


def list_reflex_actions(incident_id: str | None = None) -> List[ReflexActionRecord]:
    with connect(incident_id) as conn:
        rows = conn.execute(
            """
            SELECT id, incident_id, trigger, action, communications_alert_id, created_at
            FROM initial_reflex_actions
            ORDER BY created_at DESC
            """
        ).fetchall()
        return [ReflexActionRecord.from_row(dict(row)) for row in rows]


def update_reflex_notification(
    record_id: int,
    *,
    communications_alert_id: str,
    incident_id: str | None = None,
) -> None:
    with connect(incident_id) as conn:
        conn.execute(
            "UPDATE initial_reflex_actions SET communications_alert_id = ? WHERE id = ?",
            (communications_alert_id, record_id),
        )


def update_hasty_task_logistics(
    record_id: int,
    *,
    logistics_request_id: str,
    incident_id: str | None = None,
) -> None:
    with connect(incident_id) as conn:
        conn.execute(
            "UPDATE initial_hasty_tasks SET logistics_request_id = ? WHERE id = ?",
            (logistics_request_id, record_id),
        )


def _require_incident_id() -> str:
    incident_id = incident_context.get_active_incident_id()
    if not incident_id:
        raise RuntimeError("Active incident is not set")
    return incident_id
