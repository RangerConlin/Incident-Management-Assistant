"""SQLite repository for the Logistics resource status board."""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from typing import Any, Iterable, Optional

from utils.db import get_incident_conn

from .models import ResourceAuditEntry, ResourceItem

RESOURCE_STATUS_SCHEMA = """
CREATE TABLE IF NOT EXISTS logistics_resource_status_items (
    id TEXT PRIMARY KEY,
    resource_id TEXT NOT NULL,
    resource_name TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    status TEXT NOT NULL,
    eta_utc TEXT,
    assigned_to TEXT,
    assignment_reference TEXT,
    location TEXT,
    checked_in_time TEXT,
    last_updated TEXT NOT NULL,
    notes TEXT,
    source_entity_type TEXT,
    source_record_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_resource_status_status
    ON logistics_resource_status_items(status);
CREATE INDEX IF NOT EXISTS idx_resource_status_type
    ON logistics_resource_status_items(resource_type);
CREATE INDEX IF NOT EXISTS idx_resource_status_source
    ON logistics_resource_status_items(source_entity_type, source_record_id);

CREATE TABLE IF NOT EXISTS logistics_resource_status_audit (
    id TEXT PRIMARY KEY,
    resource_status_id TEXT NOT NULL,
    field_name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    actor_name TEXT,
    changed_at TEXT NOT NULL,
    FOREIGN KEY(resource_status_id) REFERENCES logistics_resource_status_items(id)
);

CREATE INDEX IF NOT EXISTS idx_resource_status_audit_resource
    ON logistics_resource_status_audit(resource_status_id, changed_at DESC);
"""


class ResourceStatusRepository:
    """Persist and query resource status board rows in the active incident DB."""

    def ensure_schema(self, conn: Optional[sqlite3.Connection] = None) -> None:
        if conn is None:
            with get_incident_conn() as managed:
                managed.executescript(RESOURCE_STATUS_SCHEMA)
                managed.commit()
            return
        conn.executescript(RESOURCE_STATUS_SCHEMA)

    def list_resources(self) -> list[ResourceItem]:
        with get_incident_conn() as conn:
            self.ensure_schema(conn)
            rows = conn.execute(
                """
                SELECT *
                FROM logistics_resource_status_items
                ORDER BY resource_type COLLATE NOCASE, resource_name COLLATE NOCASE, resource_id COLLATE NOCASE
                """
            ).fetchall()
        return [ResourceItem.from_row(dict(row)) for row in rows]

    def get_resource(self, resource_status_id: str) -> Optional[ResourceItem]:
        with get_incident_conn() as conn:
            self.ensure_schema(conn)
            row = conn.execute(
                "SELECT * FROM logistics_resource_status_items WHERE id = ?",
                (resource_status_id,),
            ).fetchone()
        return ResourceItem.from_row(dict(row)) if row else None

    def get_by_source(self, source_entity_type: str, source_record_id: str) -> Optional[ResourceItem]:
        with get_incident_conn() as conn:
            self.ensure_schema(conn)
            row = conn.execute(
                """
                SELECT *
                FROM logistics_resource_status_items
                WHERE source_entity_type = ? AND source_record_id = ?
                """,
                (source_entity_type, source_record_id),
            ).fetchone()
        return ResourceItem.from_row(dict(row)) if row else None

    def save_resource(self, item: ResourceItem) -> ResourceItem:
        payload = item.to_row()
        with get_incident_conn() as conn:
            self.ensure_schema(conn)
            conn.execute(
                """
                INSERT OR REPLACE INTO logistics_resource_status_items (
                    id, resource_id, resource_name, resource_type, status, eta_utc,
                    assigned_to, assignment_reference, location, checked_in_time,
                    last_updated, notes, source_entity_type, source_record_id,
                    created_at, updated_at
                ) VALUES (
                    :id, :resource_id, :resource_name, :resource_type, :status, :eta_utc,
                    :assigned_to, :assignment_reference, :location, :checked_in_time,
                    :last_updated, :notes, :source_entity_type, :source_record_id,
                    :created_at, :updated_at
                )
                """,
                payload,
            )
            conn.commit()
        return item

    def save_audit_entries(self, entries: Iterable[ResourceAuditEntry]) -> None:
        entries = list(entries)
        if not entries:
            return
        with get_incident_conn() as conn:
            self.ensure_schema(conn)
            conn.executemany(
                """
                INSERT INTO logistics_resource_status_audit (
                    id, resource_status_id, field_name, old_value, new_value,
                    actor_name, changed_at
                ) VALUES (
                    :id, :resource_status_id, :field_name, :old_value, :new_value,
                    :actor_name, :changed_at
                )
                """,
                [entry.to_row() for entry in entries],
            )
            conn.commit()

    def list_audit_entries(self, resource_status_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with get_incident_conn() as conn:
            self.ensure_schema(conn)
            rows = conn.execute(
                """
                SELECT *
                FROM logistics_resource_status_audit
                WHERE resource_status_id = ?
                ORDER BY changed_at DESC
                LIMIT ?
                """,
                (resource_status_id, int(limit)),
            ).fetchall()
        return [dict(row) for row in rows]

    def source_rows(self) -> list[dict[str, Any]]:
        """Collect incident-scoped resources that can seed the status board."""

        with get_incident_conn() as conn:
            self.ensure_schema(conn)
            sources: list[dict[str, Any]] = []
            sources.extend(self._collect_table_rows(conn, "personnel", "personnel"))
            sources.extend(self._collect_table_rows(conn, "vehicles", "vehicle"))
            sources.extend(self._collect_table_rows(conn, "equipment", "equipment"))
            sources.extend(self._collect_table_rows(conn, "aircraft", "aircraft"))
            return sources

    def _collect_table_rows(
        self,
        conn: sqlite3.Connection,
        table_name: str,
        entity_type: str,
    ) -> list[dict[str, Any]]:
        try:
            info = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        except sqlite3.OperationalError:
            return []
        if not info:
            return []

        columns = [row[1] for row in info]
        identifier = self._pick_column(columns, "id", "person_id", "tail_number", "serial_number")
        if identifier is None:
            return []
        rows = conn.execute(f"SELECT * FROM {table_name}").fetchall()
        return [
            {
                "entity_type": entity_type,
                "table_name": table_name,
                "identifier_column": identifier,
                "record": dict(row),
            }
            for row in rows
        ]

    @staticmethod
    def _pick_column(columns: list[str], *candidates: str) -> Optional[str]:
        lowered = {name.lower(): name for name in columns}
        for candidate in candidates:
            match = lowered.get(candidate.lower())
            if match:
                return match
        return columns[0] if columns else None


def new_identifier() -> str:
    return uuid.uuid4().hex


def now_local_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
