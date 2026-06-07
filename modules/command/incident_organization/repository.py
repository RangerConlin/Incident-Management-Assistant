from __future__ import annotations

"""SQLite repository for incident organization management."""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from .models import (
    ACTIVE_ASSIGNMENT_TYPES,
    AssignmentHistoryEntry,
    GeneratedFormSnapshot,
    OrganizationPosition,
    PositionAssignment,
)


def _data_dir() -> Path:
    return Path(os.environ.get("CHECKIN_DATA_DIR", "data"))


def _incident_db_path(incident_id: str) -> Path:
    safe_id = str(incident_id).strip().replace("/", "-")
    if not safe_id:
        raise ValueError("incident identifier must not be empty")
    base = _data_dir() / "incidents"
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{safe_id}.db"


def get_incident_connection(incident_id: str) -> sqlite3.Connection:
    conn = sqlite3.connect(_incident_db_path(incident_id))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _qualification_text(values: Sequence[str] | str | None) -> str:
    if values is None:
        return "[]"
    if isinstance(values, str):
        values = [v.strip() for v in values.split(",") if v.strip()]
    return json.dumps(list(values))


def _qualification_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return [part.strip() for part in value.split(",") if part.strip()]
    return [str(item) for item in parsed if str(item).strip()]


class IncidentOrganizationRepository:
    """Persists the incident organization as structured data."""

    def __init__(self, incident_id: str):
        self.incident_id = str(incident_id)
        self.ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        return get_incident_connection(self.incident_id)

    def ensure_schema(self) -> None:
        """Create organization management tables for the incident database."""

        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS organization_positions (
                    id INTEGER PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    classification TEXT NOT NULL DEFAULT 'position',
                    parent_position_id INTEGER,
                    operational_period TEXT,
                    required_qualifications TEXT NOT NULL DEFAULT '[]',
                    is_critical INTEGER NOT NULL DEFAULT 0,
                    is_custom INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'active',
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    notes TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(parent_position_id)
                        REFERENCES organization_positions(id) ON DELETE SET NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_org_positions_incident_parent
                ON organization_positions(incident_id, parent_position_id, status)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS position_assignments (
                    id INTEGER PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    position_id INTEGER NOT NULL,
                    personnel_id TEXT,
                    display_name TEXT NOT NULL,
                    assignment_type TEXT NOT NULL DEFAULT 'primary',
                    start_time TEXT,
                    end_time TEXT,
                    operational_period TEXT,
                    assigned_by TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(position_id)
                        REFERENCES organization_positions(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_position_assignments_active
                ON position_assignments(incident_id, position_id, end_time)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS position_assignment_history (
                    id INTEGER PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    assignment_id INTEGER,
                    position_id INTEGER NOT NULL,
                    personnel_id TEXT,
                    display_name TEXT NOT NULL,
                    assignment_type TEXT NOT NULL,
                    action TEXT NOT NULL,
                    effective_time TEXT,
                    operational_period TEXT,
                    changed_by TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_position_assignment_history_position
                ON position_assignment_history(incident_id, position_id, created_at)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS position_requirements (
                    id INTEGER PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    position_id INTEGER NOT NULL,
                    qualification TEXT NOT NULL,
                    is_required INTEGER NOT NULL DEFAULT 1,
                    notes TEXT,
                    FOREIGN KEY(position_id)
                        REFERENCES organization_positions(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS organization_templates (
                    id INTEGER PRIMARY KEY,
                    incident_id TEXT,
                    name TEXT NOT NULL,
                    description TEXT,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS generated_form_snapshots (
                    id INTEGER PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    form_type TEXT NOT NULL,
                    generated_at TEXT NOT NULL,
                    operational_period TEXT,
                    source_version TEXT,
                    payload TEXT NOT NULL
                )
                """
            )

    # ------------------------------------------------------------------
    def upsert_position(self, position: OrganizationPosition) -> int:
        qualifications = _qualification_text(position.required_qualifications)
        now = _utc_now()
        with self._connect() as conn:
            if position.id is None:
                cur = conn.execute(
                    """
                    INSERT INTO organization_positions (
                        incident_id, title, classification, parent_position_id,
                        operational_period, required_qualifications, is_critical,
                        is_custom, status, sort_order, notes, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.incident_id,
                        position.title,
                        position.classification,
                        position.parent_position_id,
                        position.operational_period,
                        qualifications,
                        int(position.is_critical),
                        int(position.is_custom),
                        position.status,
                        position.sort_order,
                        position.notes,
                        now,
                        now,
                    ),
                )
                return int(cur.lastrowid)
            conn.execute(
                """
                UPDATE organization_positions
                SET title=?, classification=?, parent_position_id=?,
                    operational_period=?, required_qualifications=?, is_critical=?,
                    is_custom=?, status=?, sort_order=?, notes=?, updated_at=?
                WHERE id=? AND incident_id=?
                """,
                (
                    position.title,
                    position.classification,
                    position.parent_position_id,
                    position.operational_period,
                    qualifications,
                    int(position.is_critical),
                    int(position.is_custom),
                    position.status,
                    position.sort_order,
                    position.notes,
                    now,
                    position.id,
                    self.incident_id,
                ),
            )
            return int(position.id)

    def list_positions(self, include_inactive: bool = False) -> list[OrganizationPosition]:
        sql = "SELECT * FROM organization_positions WHERE incident_id=?"
        params: list[object] = [self.incident_id]
        if not include_inactive:
            sql += " AND status='active'"
        sql += " ORDER BY parent_position_id IS NOT NULL, sort_order, title"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_position(row) for row in rows]

    def get_position(self, position_id: int) -> OrganizationPosition | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM organization_positions WHERE id=? AND incident_id=?",
                (position_id, self.incident_id),
            ).fetchone()
        return self._row_to_position(row) if row else None

    def move_position(self, position_id: int, parent_position_id: int | None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE organization_positions
                SET parent_position_id=?, updated_at=?
                WHERE id=? AND incident_id=?
                """,
                (parent_position_id, _utc_now(), position_id, self.incident_id),
            )

    def deactivate_position(self, position_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE organization_positions
                SET status='inactive', updated_at=?
                WHERE id=? AND incident_id=?
                """,
                (_utc_now(), position_id, self.incident_id),
            )

    # ------------------------------------------------------------------
    def add_assignment(self, assignment: PositionAssignment) -> int:
        assignment_type = assignment.assignment_type.lower().strip() or "primary"
        if assignment_type not in ACTIVE_ASSIGNMENT_TYPES:
            raise ValueError(f"Unsupported assignment type: {assignment.assignment_type}")
        now = _utc_now()
        start_time = assignment.start_time or now
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO position_assignments (
                    incident_id, position_id, personnel_id, display_name,
                    assignment_type, start_time, end_time, operational_period,
                    assigned_by, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.incident_id,
                    assignment.position_id,
                    assignment.personnel_id,
                    assignment.display_name,
                    assignment_type,
                    start_time,
                    assignment.end_time,
                    assignment.operational_period,
                    assignment.assigned_by,
                    assignment.notes,
                    now,
                    now,
                ),
            )
            assignment_id = int(cur.lastrowid)
            self._insert_history(
                conn,
                AssignmentHistoryEntry(
                    id=None,
                    incident_id=self.incident_id,
                    assignment_id=assignment_id,
                    position_id=assignment.position_id,
                    personnel_id=assignment.personnel_id,
                    display_name=assignment.display_name,
                    assignment_type=assignment_type,
                    action="assigned",
                    effective_time=start_time,
                    operational_period=assignment.operational_period,
                    changed_by=assignment.assigned_by,
                    notes=assignment.notes,
                ),
            )
            return assignment_id

    def end_assignment(
        self,
        assignment_id: int,
        *,
        end_time: str | None = None,
        changed_by: str | None = None,
        notes: str | None = None,
    ) -> None:
        effective = end_time or _utc_now()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM position_assignments WHERE id=? AND incident_id=?",
                (assignment_id, self.incident_id),
            ).fetchone()
            if row is None:
                return
            conn.execute(
                """
                UPDATE position_assignments
                SET end_time=?, updated_at=?, notes=COALESCE(?, notes)
                WHERE id=? AND incident_id=?
                """,
                (effective, _utc_now(), notes, assignment_id, self.incident_id),
            )
            self._insert_history(
                conn,
                AssignmentHistoryEntry(
                    id=None,
                    incident_id=self.incident_id,
                    assignment_id=assignment_id,
                    position_id=int(row["position_id"]),
                    personnel_id=row["personnel_id"],
                    display_name=row["display_name"],
                    assignment_type=row["assignment_type"],
                    action="removed",
                    effective_time=effective,
                    operational_period=row["operational_period"],
                    changed_by=changed_by,
                    notes=notes,
                ),
            )

    def list_assignments(
        self, position_id: int | None = None, *, active_only: bool = True
    ) -> list[PositionAssignment]:
        sql = "SELECT * FROM position_assignments WHERE incident_id=?"
        params: list[object] = [self.incident_id]
        if position_id is not None:
            sql += " AND position_id=?"
            params.append(position_id)
        if active_only:
            sql += " AND end_time IS NULL"
        sql += " ORDER BY position_id, start_time, id"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_assignment(row) for row in rows]

    def list_assignment_history(
        self, position_id: int | None = None
    ) -> list[AssignmentHistoryEntry]:
        sql = "SELECT * FROM position_assignment_history WHERE incident_id=?"
        params: list[object] = [self.incident_id]
        if position_id is not None:
            sql += " AND position_id=?"
            params.append(position_id)
        sql += " ORDER BY created_at, id"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_history(row) for row in rows]

    def replace_requirements(self, position_id: int, qualifications: Iterable[str]) -> None:
        clean = [q.strip() for q in qualifications if q and q.strip()]
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM position_requirements WHERE incident_id=? AND position_id=?",
                (self.incident_id, position_id),
            )
            for qualification in clean:
                conn.execute(
                    """
                    INSERT INTO position_requirements (
                        incident_id, position_id, qualification, is_required
                    ) VALUES (?, ?, ?, 1)
                    """,
                    (self.incident_id, position_id, qualification),
                )
            conn.execute(
                """
                UPDATE organization_positions
                SET required_qualifications=?, updated_at=?
                WHERE id=? AND incident_id=?
                """,
                (_qualification_text(clean), _utc_now(), position_id, self.incident_id),
            )

    def save_generated_snapshot(self, snapshot: GeneratedFormSnapshot) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO generated_form_snapshots (
                    incident_id, form_type, generated_at, operational_period,
                    source_version, payload
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    self.incident_id,
                    snapshot.form_type,
                    snapshot.generated_at,
                    snapshot.operational_period,
                    snapshot.source_version,
                    json.dumps(snapshot.payload),
                ),
            )
            return int(cur.lastrowid)

    # ------------------------------------------------------------------
    def _insert_history(self, conn: sqlite3.Connection, entry: AssignmentHistoryEntry) -> None:
        conn.execute(
            """
            INSERT INTO position_assignment_history (
                incident_id, assignment_id, position_id, personnel_id,
                display_name, assignment_type, action, effective_time,
                operational_period, changed_by, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.incident_id,
                entry.assignment_id,
                entry.position_id,
                entry.personnel_id,
                entry.display_name,
                entry.assignment_type,
                entry.action,
                entry.effective_time,
                entry.operational_period,
                entry.changed_by,
                entry.notes,
            ),
        )

    @staticmethod
    def _row_to_position(row: sqlite3.Row) -> OrganizationPosition:
        return OrganizationPosition(
            id=int(row["id"]),
            incident_id=row["incident_id"],
            title=row["title"],
            classification=row["classification"],
            parent_position_id=row["parent_position_id"],
            operational_period=row["operational_period"],
            required_qualifications=_qualification_list(row["required_qualifications"]),
            is_critical=bool(row["is_critical"]),
            is_custom=bool(row["is_custom"]),
            status=row["status"],
            sort_order=int(row["sort_order"] or 0),
            notes=row["notes"],
        )

    @staticmethod
    def _row_to_assignment(row: sqlite3.Row) -> PositionAssignment:
        return PositionAssignment(
            id=int(row["id"]),
            incident_id=row["incident_id"],
            position_id=int(row["position_id"]),
            personnel_id=row["personnel_id"],
            display_name=row["display_name"],
            assignment_type=row["assignment_type"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            operational_period=row["operational_period"],
            assigned_by=row["assigned_by"],
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_history(row: sqlite3.Row) -> AssignmentHistoryEntry:
        return AssignmentHistoryEntry(
            id=int(row["id"]),
            incident_id=row["incident_id"],
            assignment_id=row["assignment_id"],
            position_id=int(row["position_id"]),
            personnel_id=row["personnel_id"],
            display_name=row["display_name"],
            assignment_type=row["assignment_type"],
            action=row["action"],
            effective_time=row["effective_time"],
            operational_period=row["operational_period"],
            changed_by=row["changed_by"],
            notes=row["notes"],
        )
