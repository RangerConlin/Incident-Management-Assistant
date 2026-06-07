"""SQLite repository for Liaison agency coordination and feedback.

The repository owns the incident-scoped Liaison data model.  Cross-module
columns are intentionally nullable so Planning, Operations, Command, Tasks,
and Resource Requests can link to Liaison records without Liaison taking over
those modules' status workflows.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable
import json
import sqlite3

from utils import incident_context
from utils.state import AppState
from utils.db import get_incident_conn

from .models import (
    AGENCY_STATUSES,
    FEEDBACK_STATUSES,
    FEEDBACK_TYPES,
    FOLLOWUP_STATUSES,
    INTERACTION_TYPES,
    OFFER_STATUSES,
    PRIORITIES,
    REQUEST_STATUSES,
    VALIDATION_STATUSES,
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _resolve_incident_id(incident_id: object | None = None) -> str:
    value = incident_id or incident_context.get_active_incident_id() or AppState.get_active_incident()
    if not value:
        raise RuntimeError("No active incident selected for Liaison data")
    text = str(value)
    if incident_context.get_active_incident_id() != text:
        incident_context.set_active_incident(text)
    return text


def _connect(incident_id: object | None = None) -> tuple[sqlite3.Connection, str]:
    incident = _resolve_incident_id(incident_id)
    con = get_incident_conn()
    con.row_factory = sqlite3.Row
    ensure_schema(con)
    return con, incident


def _csv(values: Iterable[str]) -> str:
    return ", ".join([f"'{v}'" for v in values])


def ensure_schema(con: sqlite3.Connection) -> None:
    """Create/upgrade all Liaison tables in the active incident database."""
    con.executescript(
        f"""
        CREATE TABLE IF NOT EXISTS liaison_agencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT NOT NULL,
            name TEXT NOT NULL,
            agency_type TEXT,
            jurisdiction TEXT,
            current_status TEXT NOT NULL DEFAULT 'Not Contacted'
                CHECK (current_status IN ({_csv(AGENCY_STATUSES)})),
            assigned_liaison TEXT,
            last_contact TEXT,
            next_contact_due TEXT,
            priority TEXT DEFAULT 'Medium' CHECK (priority IN ({_csv(PRIORITIES)})),
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS liaison_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT NOT NULL,
            agency_id INTEGER,
            name TEXT NOT NULL,
            role TEXT,
            phone TEXT,
            email TEXT,
            radio_channel TEXT,
            preferred_contact TEXT,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (agency_id) REFERENCES liaison_agencies(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS liaison_interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT NOT NULL,
            agency_id INTEGER,
            contact_id INTEGER,
            interaction_type TEXT NOT NULL CHECK (interaction_type IN ({_csv(INTERACTION_TYPES)})),
            occurred_at TEXT NOT NULL,
            subject TEXT,
            summary TEXT,
            entered_by TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            objective_id INTEGER,
            strategy_id INTEGER,
            task_id INTEGER,
            resource_request_id INTEGER,
            FOREIGN KEY (agency_id) REFERENCES liaison_agencies(id) ON DELETE SET NULL,
            FOREIGN KEY (contact_id) REFERENCES liaison_contacts(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS liaison_agency_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT NOT NULL,
            agency_id INTEGER,
            contact_id INTEGER,
            interaction_id INTEGER,
            request_summary TEXT NOT NULL,
            priority TEXT DEFAULT 'Medium' CHECK (priority IN ({_csv(PRIORITIES)})),
            status TEXT DEFAULT 'Open' CHECK (status IN ({_csv(REQUEST_STATUSES)})),
            assigned_to TEXT,
            due_at TEXT,
            resource_request_id INTEGER,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (agency_id) REFERENCES liaison_agencies(id) ON DELETE SET NULL,
            FOREIGN KEY (contact_id) REFERENCES liaison_contacts(id) ON DELETE SET NULL,
            FOREIGN KEY (interaction_id) REFERENCES liaison_interactions(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS liaison_resource_offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT NOT NULL,
            agency_id INTEGER,
            contact_id INTEGER,
            interaction_id INTEGER,
            offer_summary TEXT NOT NULL,
            quantity TEXT,
            availability TEXT,
            priority TEXT DEFAULT 'Medium' CHECK (priority IN ({_csv(PRIORITIES)})),
            status TEXT DEFAULT 'Offered' CHECK (status IN ({_csv(OFFER_STATUSES)})),
            resource_request_id INTEGER,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (agency_id) REFERENCES liaison_agencies(id) ON DELETE SET NULL,
            FOREIGN KEY (contact_id) REFERENCES liaison_contacts(id) ON DELETE SET NULL,
            FOREIGN KEY (interaction_id) REFERENCES liaison_interactions(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS liaison_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT NOT NULL,
            agency_id INTEGER,
            contact_id INTEGER,
            feedback_type TEXT NOT NULL CHECK (feedback_type IN ({_csv(FEEDBACK_TYPES)})),
            priority TEXT DEFAULT 'Medium' CHECK (priority IN ({_csv(PRIORITIES)})),
            summary TEXT NOT NULL,
            requested_action TEXT,
            assigned_section TEXT,
            assigned_to TEXT,
            status TEXT DEFAULT 'Open' CHECK (status IN ({_csv(FEEDBACK_STATUSES)})),
            interaction_id INTEGER,
            objective_id INTEGER,
            strategy_id INTEGER,
            task_id INTEGER,
            resource_request_id INTEGER,
            validation_status TEXT DEFAULT 'Pending Feedback'
                CHECK (validation_status IN ({_csv(VALIDATION_STATUSES)})),
            followup_due TEXT,
            entered_by TEXT,
            entered_ts TEXT NOT NULL,
            resolved_by TEXT,
            resolved_ts TEXT,
            resolution_notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (agency_id) REFERENCES liaison_agencies(id) ON DELETE SET NULL,
            FOREIGN KEY (contact_id) REFERENCES liaison_contacts(id) ON DELETE SET NULL,
            FOREIGN KEY (interaction_id) REFERENCES liaison_interactions(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS liaison_followup_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT NOT NULL,
            agency_id INTEGER,
            contact_id INTEGER,
            interaction_id INTEGER,
            feedback_id INTEGER,
            action_summary TEXT NOT NULL,
            assigned_to TEXT,
            due_at TEXT,
            status TEXT DEFAULT 'Open' CHECK (status IN ({_csv(FOLLOWUP_STATUSES)})),
            objective_id INTEGER,
            strategy_id INTEGER,
            task_id INTEGER,
            resource_request_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (agency_id) REFERENCES liaison_agencies(id) ON DELETE SET NULL,
            FOREIGN KEY (contact_id) REFERENCES liaison_contacts(id) ON DELETE SET NULL,
            FOREIGN KEY (interaction_id) REFERENCES liaison_interactions(id) ON DELETE SET NULL,
            FOREIGN KEY (feedback_id) REFERENCES liaison_feedback(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS liaison_restrictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT NOT NULL,
            agency_id INTEGER,
            restriction_type TEXT,
            description TEXT NOT NULL,
            effective_at TEXT,
            expires_at TEXT,
            status TEXT DEFAULT 'Active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (agency_id) REFERENCES liaison_agencies(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS liaison_agreements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT NOT NULL,
            agency_id INTEGER,
            agreement_type TEXT,
            description TEXT NOT NULL,
            effective_at TEXT,
            expires_at TEXT,
            status TEXT DEFAULT 'Active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (agency_id) REFERENCES liaison_agencies(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS liaison_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT NOT NULL,
            agency_id INTEGER,
            feedback_id INTEGER,
            interaction_id INTEGER,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            description TEXT,
            uploaded_by TEXT,
            uploaded_at TEXT NOT NULL,
            FOREIGN KEY (agency_id) REFERENCES liaison_agencies(id) ON DELETE SET NULL,
            FOREIGN KEY (feedback_id) REFERENCES liaison_feedback(id) ON DELETE SET NULL,
            FOREIGN KEY (interaction_id) REFERENCES liaison_interactions(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_utc TEXT NOT NULL,
            user_id INTEGER,
            action TEXT NOT NULL,
            detail TEXT,
            incident_number TEXT
        );
        """
    )
    _ensure_validation_columns(con)
    _ensure_indexes(con)
    con.commit()


def _ensure_validation_columns(con: sqlite3.Connection) -> None:
    """Add non-invasive validation columns when linked module tables exist.

    Liaison feedback can mark linked items as stakeholder-reviewed without
    changing their operational status.  These columns are optional hooks for
    existing Planning/Operations screens to display validation state later.
    """
    table_map = {
        "objectives": "liaison_validation_status",
        "strategies": "liaison_validation_status",
        "tasks": "liaison_validation_status",
    }
    for table, column in table_map.items():
        exists = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not exists:
            continue
        cols = {row[1] for row in con.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in cols:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT DEFAULT 'Not Reviewed'")


def _ensure_indexes(con: sqlite3.Connection) -> None:
    for table in [
        "liaison_agencies",
        "liaison_contacts",
        "liaison_interactions",
        "liaison_agency_requests",
        "liaison_resource_offers",
        "liaison_feedback",
        "liaison_followup_actions",
        "liaison_restrictions",
        "liaison_agreements",
        "liaison_attachments",
    ]:
        con.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_incident ON {table}(incident_id)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_liaison_feedback_links ON liaison_feedback(objective_id, strategy_id, task_id, resource_request_id)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_liaison_feedback_status ON liaison_feedback(status, priority)")


def _audit(con: sqlite3.Connection, incident_id: str, action: str, detail: dict[str, Any]) -> None:
    try:
        user = AppState.get_active_user_id()
        user_id = int(user) if user is not None else None
    except Exception:
        user_id = None
    con.execute(
        "INSERT INTO audit_logs (ts_utc, user_id, action, detail, incident_number) VALUES (?, ?, ?, ?, ?)",
        (now_utc(), user_id, action, json.dumps(detail, ensure_ascii=False), incident_id),
    )


def _clean_status(value: str | None, allowed: list[str], default: str) -> str:
    if not value:
        return default
    for option in allowed:
        if option.lower() == str(value).strip().lower():
            return option
    return default


def create_agency(data: dict[str, Any], incident_id: object | None = None) -> int:
    con, incident = _connect(incident_id)
    try:
        ts = now_utc()
        status = _clean_status(data.get("current_status"), AGENCY_STATUSES, "Not Contacted")
        priority = _clean_status(data.get("priority"), PRIORITIES, "Medium")
        cur = con.execute(
            """
            INSERT INTO liaison_agencies (
                incident_id, name, agency_type, jurisdiction, current_status,
                assigned_liaison, last_contact, next_contact_due, priority, notes,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                incident,
                str(data.get("name") or "").strip(),
                data.get("agency_type"),
                data.get("jurisdiction"),
                status,
                data.get("assigned_liaison"),
                data.get("last_contact"),
                data.get("next_contact_due"),
                priority,
                data.get("notes"),
                ts,
                ts,
            ),
        )
        agency_id = int(cur.lastrowid)
        _audit(con, incident, "liaison.agency.created", {"agency_id": agency_id, "name": data.get("name")})
        con.commit()
        return agency_id
    finally:
        con.close()


def update_agency_status(agency_id: int, status: str, incident_id: object | None = None) -> None:
    con, incident = _connect(incident_id)
    try:
        status = _clean_status(status, AGENCY_STATUSES, "Not Contacted")
        con.execute(
            "UPDATE liaison_agencies SET current_status=?, updated_at=? WHERE id=? AND incident_id=?",
            (status, now_utc(), int(agency_id), incident),
        )
        _audit(con, incident, "liaison.agency.status_changed", {"agency_id": agency_id, "status": status})
        con.commit()
    finally:
        con.close()


def create_interaction(data: dict[str, Any], incident_id: object | None = None) -> int:
    con, incident = _connect(incident_id)
    try:
        ts = now_utc()
        interaction_type = _clean_status(data.get("interaction_type"), INTERACTION_TYPES, "Other")
        cur = con.execute(
            """
            INSERT INTO liaison_interactions (
                incident_id, agency_id, contact_id, interaction_type, occurred_at,
                subject, summary, entered_by, created_at, updated_at,
                objective_id, strategy_id, task_id, resource_request_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                incident,
                data.get("agency_id"),
                data.get("contact_id"),
                interaction_type,
                data.get("occurred_at") or ts,
                data.get("subject"),
                data.get("summary"),
                data.get("entered_by"),
                ts,
                ts,
                data.get("objective_id"),
                data.get("strategy_id"),
                data.get("task_id"),
                data.get("resource_request_id"),
            ),
        )
        interaction_id = int(cur.lastrowid)
        if data.get("agency_id"):
            con.execute(
                "UPDATE liaison_agencies SET last_contact=?, updated_at=? WHERE id=? AND incident_id=?",
                (data.get("occurred_at") or ts, ts, data.get("agency_id"), incident),
            )
        _audit(con, incident, "liaison.interaction.created", {"interaction_id": interaction_id, "type": interaction_type})
        followup = str(data.get("followup_action") or "").strip()
        if followup:
            con.execute(
                """
                INSERT INTO liaison_followup_actions (
                    incident_id, agency_id, contact_id, interaction_id, action_summary,
                    assigned_to, due_at, status, objective_id, strategy_id, task_id,
                    resource_request_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Open', ?, ?, ?, ?, ?, ?)
                """,
                (
                    incident,
                    data.get("agency_id"),
                    data.get("contact_id"),
                    interaction_id,
                    followup,
                    data.get("followup_assigned_to"),
                    data.get("followup_due"),
                    data.get("objective_id"),
                    data.get("strategy_id"),
                    data.get("task_id"),
                    data.get("resource_request_id"),
                    ts,
                    ts,
                ),
            )
            _audit(con, incident, "liaison.followup.created", {"interaction_id": interaction_id, "summary": followup})
        con.commit()
        return interaction_id
    finally:
        con.close()


def create_feedback(data: dict[str, Any], incident_id: object | None = None) -> int:
    con, incident = _connect(incident_id)
    try:
        ts = now_utc()
        feedback_type = _clean_status(data.get("feedback_type"), FEEDBACK_TYPES, "Concern")
        priority = _clean_status(data.get("priority"), PRIORITIES, "Medium")
        status = _clean_status(data.get("status"), FEEDBACK_STATUSES, "Open")
        validation = _clean_status(data.get("validation_status"), VALIDATION_STATUSES, "Pending Feedback")
        cur = con.execute(
            """
            INSERT INTO liaison_feedback (
                incident_id, agency_id, contact_id, feedback_type, priority, summary,
                requested_action, assigned_section, assigned_to, status, interaction_id,
                objective_id, strategy_id, task_id, resource_request_id,
                validation_status, followup_due, entered_by, entered_ts, resolved_by,
                resolved_ts, resolution_notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                incident,
                data.get("agency_id"),
                data.get("contact_id"),
                feedback_type,
                priority,
                str(data.get("summary") or "").strip(),
                data.get("requested_action"),
                data.get("assigned_section"),
                data.get("assigned_to"),
                status,
                data.get("interaction_id"),
                data.get("objective_id"),
                data.get("strategy_id"),
                data.get("task_id"),
                data.get("resource_request_id"),
                validation,
                data.get("followup_due"),
                data.get("entered_by"),
                data.get("entered_ts") or ts,
                data.get("resolved_by"),
                data.get("resolved_ts"),
                data.get("resolution_notes"),
                ts,
                ts,
            ),
        )
        feedback_id = int(cur.lastrowid)
        _audit(con, incident, "liaison.feedback.created", {"feedback_id": feedback_id, "type": feedback_type})
        followup = str(data.get("followup_action") or "").strip()
        if followup:
            con.execute(
                """
                INSERT INTO liaison_followup_actions (
                    incident_id, agency_id, contact_id, interaction_id, feedback_id,
                    action_summary, assigned_to, due_at, status, objective_id,
                    strategy_id, task_id, resource_request_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Open', ?, ?, ?, ?, ?, ?)
                """,
                (
                    incident,
                    data.get("agency_id"),
                    data.get("contact_id"),
                    data.get("interaction_id"),
                    feedback_id,
                    followup,
                    data.get("assigned_to"),
                    data.get("followup_due"),
                    data.get("objective_id"),
                    data.get("strategy_id"),
                    data.get("task_id"),
                    data.get("resource_request_id"),
                    ts,
                    ts,
                ),
            )
            _audit(con, incident, "liaison.followup.created", {"feedback_id": feedback_id, "summary": followup})
        con.commit()
        return feedback_id
    finally:
        con.close()


def fetch_agency_rows(incident_id: object | None = None) -> list[dict[str, Any]]:
    con, incident = _connect(incident_id)
    try:
        rows = con.execute(
            """
            SELECT
                a.id,
                a.name AS agency_name,
                a.agency_type,
                a.jurisdiction,
                a.current_status,
                a.assigned_liaison,
                a.last_contact,
                a.next_contact_due,
                a.priority,
                COALESCE(req.open_requests, 0) AS open_requests,
                COALESCE(off.resource_offers, 0) AS resource_offers,
                COALESCE(fb.open_feedback_items, 0) AS open_feedback_items
            FROM liaison_agencies a
            LEFT JOIN (
                SELECT agency_id, COUNT(*) AS open_requests
                FROM liaison_agency_requests
                WHERE incident_id=? AND status NOT IN ('Closed', 'Cancelled', 'Filled', 'Declined')
                GROUP BY agency_id
            ) req ON req.agency_id = a.id
            LEFT JOIN (
                SELECT agency_id, COUNT(*) AS resource_offers
                FROM liaison_resource_offers
                WHERE incident_id=? AND status NOT IN ('Declined', 'Released')
                GROUP BY agency_id
            ) off ON off.agency_id = a.id
            LEFT JOIN (
                SELECT agency_id, COUNT(*) AS open_feedback_items
                FROM liaison_feedback
                WHERE incident_id=? AND status NOT IN ('Closed', 'Cancelled', 'Resolved')
                GROUP BY agency_id
            ) fb ON fb.agency_id = a.id
            WHERE a.incident_id=?
            ORDER BY CASE a.priority WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END,
                     a.next_contact_due IS NULL, a.next_contact_due, a.name
            """,
            (incident, incident, incident, incident),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        con.close()


def fetch_feedback_rows(incident_id: object | None = None) -> list[dict[str, Any]]:
    con, incident = _connect(incident_id)
    try:
        rows = con.execute(
            """
            SELECT
                f.id,
                f.entered_ts AS date_time,
                COALESCE(a.name, 'Unassigned source') AS source,
                f.feedback_type,
                f.priority,
                CASE
                    WHEN f.task_id IS NOT NULL THEN 'Task #' || f.task_id
                    WHEN f.objective_id IS NOT NULL THEN 'Objective #' || f.objective_id
                    WHEN f.strategy_id IS NOT NULL THEN 'Strategy #' || f.strategy_id
                    WHEN f.resource_request_id IS NOT NULL THEN 'Resource Request #' || f.resource_request_id
                    ELSE 'Unlinked'
                END AS linked_item,
                f.status,
                COALESCE(NULLIF(f.assigned_to, ''), f.assigned_section, '') AS assigned_to,
                f.followup_due AS due_followup,
                CASE
                    WHEN f.status IN ('Resolved', 'Closed') THEN COALESCE(NULLIF(f.resolution_notes, ''), f.status)
                    ELSE f.validation_status
                END AS resolution_status,
                f.summary,
                f.validation_status,
                f.agency_id,
                f.contact_id,
                f.interaction_id,
                f.objective_id,
                f.strategy_id,
                f.task_id,
                f.resource_request_id
            FROM liaison_feedback f
            LEFT JOIN liaison_agencies a ON a.id = f.agency_id
            WHERE f.incident_id=?
            ORDER BY CASE f.priority WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END,
                     f.entered_ts DESC
            """,
            (incident,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        con.close()


def fetch_agency_detail(agency_id: int, incident_id: object | None = None) -> dict[str, Any]:
    con, incident = _connect(incident_id)
    try:
        agency = con.execute(
            "SELECT * FROM liaison_agencies WHERE id=? AND incident_id=?",
            (int(agency_id), incident),
        ).fetchone()
        if agency is None:
            raise ValueError(f"Liaison agency {agency_id} was not found")
        tables = {
            "contacts": "liaison_contacts",
            "interactions": "liaison_interactions",
            "requests": "liaison_agency_requests",
            "offers": "liaison_resource_offers",
            "feedback": "liaison_feedback",
            "restrictions": "liaison_restrictions",
            "agreements": "liaison_agreements",
            "attachments": "liaison_attachments",
        }
        detail: dict[str, Any] = {"agency": dict(agency)}
        for key, table in tables.items():
            detail[key] = [
                dict(row)
                for row in con.execute(
                    f"SELECT * FROM {table} WHERE incident_id=? AND agency_id=? ORDER BY id DESC",
                    (incident, int(agency_id)),
                ).fetchall()
            ]
        detail["audit"] = [
            dict(row)
            for row in con.execute(
                "SELECT * FROM audit_logs WHERE incident_number=? AND detail LIKE ? ORDER BY id DESC LIMIT 100",
                (incident, f'%"agency_id": {int(agency_id)}%'),
            ).fetchall()
        ]
        return detail
    finally:
        con.close()


def fetch_feedback_for_objective(objective_id: int, incident_id: object | None = None) -> list[dict[str, Any]]:
    return _fetch_feedback_by_link("objective_id", objective_id, incident_id)


def fetch_feedback_for_strategy(strategy_id: int, incident_id: object | None = None) -> list[dict[str, Any]]:
    return _fetch_feedback_by_link("strategy_id", strategy_id, incident_id)


def fetch_feedback_for_task(task_id: int, incident_id: object | None = None) -> list[dict[str, Any]]:
    return _fetch_feedback_by_link("task_id", task_id, incident_id)


def fetch_feedback_for_resource_request(resource_request_id: int, incident_id: object | None = None) -> list[dict[str, Any]]:
    return _fetch_feedback_by_link("resource_request_id", resource_request_id, incident_id)


def _fetch_feedback_by_link(column: str, value: int, incident_id: object | None) -> list[dict[str, Any]]:
    allowed = {"objective_id", "strategy_id", "task_id", "resource_request_id"}
    if column not in allowed:
        raise ValueError("Unsupported Liaison feedback link")
    con, incident = _connect(incident_id)
    try:
        rows = con.execute(
            f"""
            SELECT f.*, COALESCE(a.name, '') AS source
            FROM liaison_feedback f
            LEFT JOIN liaison_agencies a ON a.id = f.agency_id
            WHERE f.incident_id=? AND f.{column}=?
            ORDER BY f.entered_ts DESC
            """,
            (incident, int(value)),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        con.close()


__all__ = [
    "ensure_schema",
    "create_agency",
    "update_agency_status",
    "create_interaction",
    "create_feedback",
    "fetch_agency_rows",
    "fetch_feedback_rows",
    "fetch_agency_detail",
    "fetch_feedback_for_objective",
    "fetch_feedback_for_strategy",
    "fetch_feedback_for_task",
    "fetch_feedback_for_resource_request",
]
