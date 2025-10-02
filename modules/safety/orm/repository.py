"""SQLite persistence helpers for the CAP ORM module."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from utils.audit import now_utc_iso
from utils.state import AppState

from .models import ORMForm, ORMHazard

DATA_DIR = Path(os.environ.get("CHECKIN_DATA_DIR", "data")) / "incidents"

RISK_LEVELS: Sequence[str] = ("L", "M", "H", "EH")


def _db_path_for_incident(incident_id: int | str) -> Path:
    return DATA_DIR / f"{incident_id}.db"


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS orm_form (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER NOT NULL,
            op_period INTEGER NOT NULL,
            activity TEXT NULL,
            prepared_by_id INTEGER NULL,
            date_iso TEXT NULL,
            highest_residual_risk TEXT NOT NULL DEFAULT 'L' CHECK (highest_residual_risk IN ('L','M','H','EH')),
            status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','pending_mitigation','approved')),
            approval_blocked INTEGER NOT NULL DEFAULT 0,
            UNIQUE(incident_id, op_period)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS orm_hazards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            form_id INTEGER NOT NULL REFERENCES orm_form(id) ON DELETE CASCADE,
            sub_activity TEXT NOT NULL,
            hazard_outcome TEXT NOT NULL,
            initial_risk TEXT NOT NULL CHECK (initial_risk IN ('L','M','H','EH')),
            control_text TEXT NOT NULL,
            residual_risk TEXT NOT NULL CHECK (residual_risk IN ('L','M','H','EH')),
            implement_how TEXT NULL,
            implement_who TEXT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_orm_hazards_form_id ON orm_hazards(form_id)"
    )
    _ensure_audit_schema(conn)
    conn.commit()


def _ensure_audit_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER,
            user_id INTEGER,
            ts_iso TEXT,
            entity TEXT,
            entity_id INTEGER,
            action TEXT,
            field TEXT,
            old_value TEXT,
            new_value TEXT
        )
        """
    )
    cur = conn.execute("PRAGMA table_info(audit_logs)")
    existing = {row[1] for row in cur.fetchall()}
    required = {
        "incident_id": "INTEGER",
        "user_id": "INTEGER",
        "ts_iso": "TEXT",
        "entity": "TEXT",
        "entity_id": "INTEGER",
        "action": "TEXT",
        "field": "TEXT",
        "old_value": "TEXT",
        "new_value": "TEXT",
    }
    for column, col_type in required.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE audit_logs ADD COLUMN {column} {col_type}")
    conn.commit()


@contextmanager
def incident_connection(incident_id: int | str) -> Iterator[sqlite3.Connection]:
    path = _db_path_for_incident(incident_id)
    conn = _connect(path)
    try:
        _ensure_schema(conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _row_to_form(row: sqlite3.Row) -> ORMForm:
    return ORMForm(
        id=row["id"],
        incident_id=row["incident_id"],
        op_period=row["op_period"],
        activity=row["activity"],
        prepared_by_id=row["prepared_by_id"],
        date_iso=row["date_iso"],
        highest_residual_risk=row["highest_residual_risk"],
        status=row["status"],
        approval_blocked=bool(row["approval_blocked"]),
    )


def _row_to_hazard(row: sqlite3.Row) -> ORMHazard:
    return ORMHazard(
        id=row["id"],
        form_id=row["form_id"],
        sub_activity=row["sub_activity"],
        hazard_outcome=row["hazard_outcome"],
        initial_risk=row["initial_risk"],
        control_text=row["control_text"],
        residual_risk=row["residual_risk"],
        implement_how=row["implement_how"],
        implement_who=row["implement_who"],
    )


def fetch_form(conn: sqlite3.Connection, incident_id: int, op_period: int) -> ORMForm | None:
    cur = conn.execute(
        "SELECT * FROM orm_form WHERE incident_id = ? AND op_period = ?",
        (incident_id, op_period),
    )
    row = cur.fetchone()
    return _row_to_form(row) if row else None


def fetch_form_by_id(conn: sqlite3.Connection, form_id: int) -> ORMForm | None:
    cur = conn.execute("SELECT * FROM orm_form WHERE id = ?", (form_id,))
    row = cur.fetchone()
    return _row_to_form(row) if row else None


def insert_form(conn: sqlite3.Connection, incident_id: int, op_period: int) -> ORMForm:
    cur = conn.execute(
        "INSERT INTO orm_form (incident_id, op_period) VALUES (?, ?)",
        (incident_id, op_period),
    )
    form_id = cur.lastrowid
    form = fetch_form_by_id(conn, form_id)
    log_audit(
        conn,
        incident_id=incident_id,
        entity="orm_form",
        entity_id=form_id,
        action="create",
        field=None,
        old_value=None,
        new_value={"op_period": op_period},
    )
    return form  # type: ignore[return-value]


def update_form_fields(
    conn: sqlite3.Connection,
    form_id: int,
    updates: dict[str, Any],
) -> ORMForm:
    if not updates:
        form = fetch_form_by_id(conn, form_id)
        if form is None:
            raise KeyError(form_id)
        return form
    form = fetch_form_by_id(conn, form_id)
    if form is None:
        raise KeyError(form_id)
    assignments = ", ".join([f"{field} = ?" for field in updates.keys()])
    params = list(updates.values()) + [form_id]
    conn.execute(f"UPDATE orm_form SET {assignments} WHERE id = ?", params)
    new_form = fetch_form_by_id(conn, form_id)
    assert new_form is not None
    for key, new_val in updates.items():
        old_val = getattr(form, key)
        if old_val != new_val:
            log_audit(
                conn,
                incident_id=form.incident_id,
                entity="orm_form",
                entity_id=form_id,
                action="update",
                field=key,
                old_value=old_val,
                new_value=new_val,
            )
    return new_form


def list_hazards(conn: sqlite3.Connection, form_id: int) -> list[ORMHazard]:
    cur = conn.execute(
        "SELECT * FROM orm_hazards WHERE form_id = ? ORDER BY id",
        (form_id,),
    )
    return [_row_to_hazard(row) for row in cur.fetchall()]


def fetch_hazard(conn: sqlite3.Connection, hazard_id: int) -> ORMHazard | None:
    cur = conn.execute("SELECT * FROM orm_hazards WHERE id = ?", (hazard_id,))
    row = cur.fetchone()
    return _row_to_hazard(row) if row else None


def insert_hazard(conn: sqlite3.Connection, form_id: int, payload: dict[str, Any]) -> ORMHazard:
    fields = [
        "sub_activity",
        "hazard_outcome",
        "initial_risk",
        "control_text",
        "residual_risk",
        "implement_how",
        "implement_who",
    ]
    values = [payload.get(field) for field in fields]
    placeholders = ", ".join(["?"] * len(fields))
    cur = conn.execute(
        f"INSERT INTO orm_hazards (form_id, {', '.join(fields)}) VALUES (?, {placeholders})",
        [form_id, *values],
    )
    hazard_id = cur.lastrowid
    hazard = fetch_hazard(conn, hazard_id)
    log_audit(
        conn,
        incident_id=payload.get("incident_id") or _incident_from_form(conn, form_id),
        entity="orm_hazard",
        entity_id=hazard_id,
        action="create",
        field=None,
        old_value=None,
        new_value={k: payload.get(k) for k in fields},
    )
    return hazard  # type: ignore[return-value]


def update_hazard(
    conn: sqlite3.Connection,
    hazard_id: int,
    payload: dict[str, Any],
) -> ORMHazard:
    hazard = fetch_hazard(conn, hazard_id)
    if hazard is None:
        raise KeyError(hazard_id)
    fields = [
        "sub_activity",
        "hazard_outcome",
        "initial_risk",
        "control_text",
        "residual_risk",
        "implement_how",
        "implement_who",
    ]
    assignments = ", ".join([f"{field} = ?" for field in fields])
    values = [payload.get(field) for field in fields]
    conn.execute(
        f"UPDATE orm_hazards SET {assignments} WHERE id = ?",
        [*values, hazard_id],
    )
    updated = fetch_hazard(conn, hazard_id)
    assert updated is not None
    for field in fields:
        old_val = getattr(hazard, field)
        new_val = getattr(updated, field)
        if old_val != new_val:
            log_audit(
                conn,
                incident_id=_incident_from_form(conn, hazard.form_id),
                entity="orm_hazard",
                entity_id=hazard_id,
                action="update",
                field=field,
                old_value=old_val,
                new_value=new_val,
            )
    return updated


def delete_hazard(conn: sqlite3.Connection, hazard_id: int) -> None:
    hazard = fetch_hazard(conn, hazard_id)
    if hazard is None:
        return
    conn.execute("DELETE FROM orm_hazards WHERE id = ?", (hazard_id,))
    for field in [
        "sub_activity",
        "hazard_outcome",
        "initial_risk",
        "control_text",
        "residual_risk",
        "implement_how",
        "implement_who",
    ]:
        log_audit(
            conn,
            incident_id=_incident_from_form(conn, hazard.form_id),
            entity="orm_hazard",
            entity_id=hazard_id,
            action="delete",
            field=field,
            old_value=getattr(hazard, field),
            new_value=None,
        )


def update_form_state(
    conn: sqlite3.Connection,
    form_id: int,
    highest_residual_risk: str,
    status: str,
    approval_blocked: bool,
) -> ORMForm:
    form = fetch_form_by_id(conn, form_id)
    if form is None:
        raise KeyError(form_id)
    conn.execute(
        "UPDATE orm_form SET highest_residual_risk = ?, status = ?, approval_blocked = ? WHERE id = ?",
        (highest_residual_risk, status, int(approval_blocked), form_id),
    )
    updated = fetch_form_by_id(conn, form_id)
    assert updated is not None
    if form.highest_residual_risk != highest_residual_risk:
        log_audit(
            conn,
            incident_id=form.incident_id,
            entity="orm_form",
            entity_id=form_id,
            action="risk_recompute",
            field="highest_residual_risk",
            old_value=form.highest_residual_risk,
            new_value=highest_residual_risk,
        )
    if form.status != updated.status:
        log_audit(
            conn,
            incident_id=form.incident_id,
            entity="orm_form",
            entity_id=form_id,
            action="risk_recompute",
            field="status",
            old_value=form.status,
            new_value=updated.status,
        )
    if form.approval_blocked != updated.approval_blocked:
        log_audit(
            conn,
            incident_id=form.incident_id,
            entity="orm_form",
            entity_id=form_id,
            action="risk_recompute",
            field="approval_blocked",
            old_value=form.approval_blocked,
            new_value=updated.approval_blocked,
        )
    return updated


def _incident_from_form(conn: sqlite3.Connection, form_id: int) -> int:
    cur = conn.execute("SELECT incident_id FROM orm_form WHERE id = ?", (form_id,))
    row = cur.fetchone()
    if row is None:
        raise KeyError("form not found")
    return row[0]


def log_audit(
    conn: sqlite3.Connection,
    *,
    incident_id: int | None,
    entity: str,
    entity_id: int | None,
    action: str,
    field: str | None,
    old_value: Any,
    new_value: Any,
) -> None:
    _ensure_audit_schema(conn)
    user_id = AppState.get_active_user_id()
    payload_old = None if old_value is None else str(old_value)
    payload_new = None if new_value is None else str(new_value)
    conn.execute(
        """
        INSERT INTO audit_logs (incident_id, user_id, ts_iso, entity, entity_id, action, field, old_value, new_value)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            incident_id,
            user_id,
            now_utc_iso(),
            entity,
            entity_id,
            action,
            field,
            payload_old,
            payload_new,
        ),
    )
