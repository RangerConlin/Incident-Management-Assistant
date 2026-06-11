"""
WorkAssignmentRepository
========================
Manages all persistence for Work Assignments and their related records.

Uses raw sqlite3 (same pattern as the Taskings module) so we can use
CREATE TABLE IF NOT EXISTS and additive migrations without touching ORM.

The active incident database path is resolved at call time via incident_context
so the repository always targets the currently open incident.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from modules.planning.tactics_resources.models.work_assignment_models import (
    OUTPUT_TYPE_VALUES,
    WorkAssignment,
    WorkAssignmentComms,
    WorkAssignmentHazard,
    WorkAssignmentLogEntry,
    WorkAssignmentOutputStatus,
    WorkAssignmentResourceAssignment,
    WorkAssignmentResourceRequirement,
    WorkAssignmentTaskLink,
)


def _now() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat(sep=" ", timespec="seconds")


class WorkAssignmentRepository:
    """
    Full CRUD repository for Work Assignments.

    Usage:
        repo = WorkAssignmentRepository()          # uses active incident DB
        repo = WorkAssignmentRepository(path)      # explicit DB path for testing
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            from utils.incident_context import get_active_incident_db_path
            db_path = get_active_incident_db_path()
        self._db_path = Path(db_path)

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        """Open a connection, enforce FK constraints, commit on success."""
        con = sqlite3.connect(self._db_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    # ------------------------------------------------------------------
    # Schema initialization — safe to call on every startup
    # ------------------------------------------------------------------

    def initialize_schema(self) -> None:
        """Create all Work Assignment tables if they do not already exist."""
        with self._connect() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS work_assignments (
                    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                    assignment_number    TEXT,
                    assignment_name      TEXT NOT NULL,
                    objective_id         INTEGER,
                    operational_period_id INTEGER,
                    branch               TEXT,
                    division_group       TEXT,
                    location             TEXT,
                    assignment_kind      TEXT,
                    priority             TEXT DEFAULT 'Normal',
                    planning_status      TEXT DEFAULT 'Draft',
                    safety_status        TEXT DEFAULT 'Unchecked',
                    resource_status      TEXT DEFAULT 'Unreviewed',
                    description          TEXT,
                    tactics_summary      TEXT,
                    special_instructions TEXT,
                    prepared_by          INTEGER,
                    approved_by          INTEGER,
                    created_at           TEXT NOT NULL,
                    updated_at           TEXT NOT NULL,
                    created_by           INTEGER,
                    updated_by           INTEGER,
                    is_archived          INTEGER NOT NULL DEFAULT 0,
                    notes                TEXT
                );

                CREATE TABLE IF NOT EXISTS work_assignment_resources (
                    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                    work_assignment_id    INTEGER NOT NULL,
                    resource_type_id      INTEGER,
                    resource_type_text    TEXT NOT NULL,
                    capability_id         INTEGER,
                    capability_text       TEXT,
                    quantity_required     INTEGER NOT NULL DEFAULT 1,
                    quantity_assigned     INTEGER NOT NULL DEFAULT 0,
                    quantity_available    INTEGER NOT NULL DEFAULT 0,
                    quantity_gap          INTEGER NOT NULL DEFAULT 0,
                    unit                  TEXT,
                    priority              TEXT DEFAULT 'Normal',
                    source_note           TEXT,
                    logistics_request_id  INTEGER,
                    notes                 TEXT,
                    created_at            TEXT NOT NULL,
                    updated_at            TEXT NOT NULL,
                    FOREIGN KEY(work_assignment_id)
                        REFERENCES work_assignments(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS work_assignment_resource_assignments (
                    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
                    work_assignment_resource_id INTEGER NOT NULL,
                    resource_kind               TEXT NOT NULL,
                    resource_id                 TEXT NOT NULL,
                    display_name                TEXT,
                    status                      TEXT DEFAULT 'Planned',
                    assigned_at                 TEXT,
                    released_at                 TEXT,
                    notes                       TEXT,
                    FOREIGN KEY(work_assignment_resource_id)
                        REFERENCES work_assignment_resources(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS work_assignment_hazards (
                    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                    work_assignment_id INTEGER NOT NULL,
                    hazard_type_id     INTEGER,
                    hazard_type_text   TEXT NOT NULL,
                    category           TEXT,
                    risk_level         TEXT DEFAULT 'Unknown',
                    likelihood         TEXT DEFAULT 'Unknown',
                    severity           TEXT DEFAULT 'Unknown',
                    control_measure    TEXT,
                    mitigation_text    TEXT,
                    ppe_text           TEXT,
                    safety_message     TEXT,
                    source             TEXT,
                    is_resolved        INTEGER NOT NULL DEFAULT 0,
                    notes              TEXT,
                    created_at         TEXT NOT NULL,
                    updated_at         TEXT NOT NULL,
                    FOREIGN KEY(work_assignment_id)
                        REFERENCES work_assignments(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS work_assignment_comms (
                    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                    work_assignment_id INTEGER NOT NULL,
                    channel_id         TEXT,
                    channel_name       TEXT,
                    function           TEXT,
                    zone               TEXT,
                    channel_number     TEXT,
                    rx_freq            TEXT,
                    rx_tone            TEXT,
                    tx_freq            TEXT,
                    tx_tone            TEXT,
                    mode               TEXT,
                    remarks            TEXT,
                    is_primary         INTEGER NOT NULL DEFAULT 0,
                    notes              TEXT,
                    created_at         TEXT NOT NULL,
                    updated_at         TEXT NOT NULL,
                    FOREIGN KEY(work_assignment_id)
                        REFERENCES work_assignments(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS work_assignment_tasks (
                    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                    work_assignment_id INTEGER NOT NULL,
                    task_id            INTEGER NOT NULL,
                    link_type          TEXT DEFAULT 'Generated',
                    created_at         TEXT NOT NULL,
                    created_by         INTEGER,
                    notes              TEXT,
                    FOREIGN KEY(work_assignment_id)
                        REFERENCES work_assignments(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS work_assignment_log (
                    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                    work_assignment_id INTEGER NOT NULL,
                    timestamp          TEXT NOT NULL,
                    entered_by         INTEGER,
                    entry_type         TEXT DEFAULT 'Note',
                    entry_text         TEXT NOT NULL,
                    critical           INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(work_assignment_id)
                        REFERENCES work_assignments(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS work_assignment_outputs (
                    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                    work_assignment_id   INTEGER NOT NULL,
                    output_type          TEXT NOT NULL,
                    status               TEXT DEFAULT 'Not Started',
                    generated_file_path  TEXT,
                    generated_at         TEXT,
                    generated_by         INTEGER,
                    notes                TEXT,
                    FOREIGN KEY(work_assignment_id)
                        REFERENCES work_assignments(id) ON DELETE CASCADE
                );
            """)

    # ------------------------------------------------------------------
    # Work Assignment CRUD
    # ------------------------------------------------------------------

    def list_work_assignments(
        self,
        filters: dict[str, Any] | None = None,
    ) -> list[WorkAssignment]:
        """
        Return work assignments matching optional filters.

        Supported filter keys:
            search          (str)  — partial match on assignment_name or number
            planning_status (str)  — exact match
            safety_status   (str)  — exact match
            resource_status (str)  — exact match
            branch          (str)  — exact match
            division_group  (str)  — exact match
            op_period_id    (int)  — exact match
            show_archived   (bool) — include archived records (default False)
        """
        filters = filters or {}
        show_archived = filters.get("show_archived", False)

        clauses = ["1=1"]
        params: list[Any] = []

        if not show_archived:
            clauses.append("is_archived = 0")

        if "search" in filters and filters["search"]:
            token = f"%{filters['search']}%"
            clauses.append("(assignment_name LIKE ? OR assignment_number LIKE ?)")
            params.extend([token, token])

        for col in ("planning_status", "safety_status", "resource_status", "branch", "division_group"):
            if col in filters and filters[col]:
                clauses.append(f"{col} = ?")
                params.append(filters[col])

        if "op_period_id" in filters and filters["op_period_id"] is not None:
            clauses.append("operational_period_id = ?")
            params.append(filters["op_period_id"])

        sql = (
            "SELECT * FROM work_assignments WHERE "
            + " AND ".join(clauses)
            + " ORDER BY updated_at DESC"
        )
        with self._connect() as con:
            rows = con.execute(sql, params).fetchall()
        return [WorkAssignment.from_row(r) for r in rows]

    def get_work_assignment(self, work_assignment_id: int) -> WorkAssignment | None:
        """Return a single work assignment by ID, or None if not found."""
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM work_assignments WHERE id = ?",
                (work_assignment_id,),
            ).fetchone()
        return WorkAssignment.from_row(row) if row else None

    def create_work_assignment(self, data: dict[str, Any]) -> int:
        """
        Create a new work assignment.

        data should contain at minimum: assignment_name.
        Returns the new record ID.
        """
        now = _now()
        sql = """
            INSERT INTO work_assignments (
                assignment_number, assignment_name, objective_id,
                operational_period_id, branch, division_group, location,
                assignment_kind, priority, planning_status, safety_status,
                resource_status, description, tactics_summary, special_instructions,
                prepared_by, approved_by, created_at, updated_at,
                created_by, updated_by, is_archived, notes
            ) VALUES (
                :assignment_number, :assignment_name, :objective_id,
                :operational_period_id, :branch, :division_group, :location,
                :assignment_kind, :priority, :planning_status, :safety_status,
                :resource_status, :description, :tactics_summary, :special_instructions,
                :prepared_by, :approved_by, :created_at, :updated_at,
                :created_by, :updated_by, 0, :notes
            )
        """
        record = {
            "assignment_number": data.get("assignment_number", ""),
            "assignment_name": data.get("assignment_name", ""),
            "objective_id": data.get("objective_id"),
            "operational_period_id": data.get("operational_period_id"),
            "branch": data.get("branch", ""),
            "division_group": data.get("division_group", ""),
            "location": data.get("location", ""),
            "assignment_kind": data.get("assignment_kind", "Ground"),
            "priority": data.get("priority", "Normal"),
            "planning_status": data.get("planning_status", "Draft"),
            "safety_status": data.get("safety_status", "Unchecked"),
            "resource_status": data.get("resource_status", "Unreviewed"),
            "description": data.get("description", ""),
            "tactics_summary": data.get("tactics_summary", ""),
            "special_instructions": data.get("special_instructions", ""),
            "prepared_by": data.get("prepared_by"),
            "approved_by": data.get("approved_by"),
            "created_at": now,
            "updated_at": now,
            "created_by": data.get("created_by"),
            "updated_by": data.get("updated_by"),
            "notes": data.get("notes", ""),
        }
        with self._connect() as con:
            cur = con.execute(sql, record)
            new_id = cur.lastrowid
            # Auto-generate assignment number if not provided
            if not record["assignment_number"]:
                con.execute(
                    "UPDATE work_assignments SET assignment_number = ? WHERE id = ?",
                    (f"ST-{new_id}", new_id),
                )
            # Seed output-readiness rows for all standard output types
            for output_type in OUTPUT_TYPE_VALUES:
                con.execute(
                    """INSERT INTO work_assignment_outputs
                       (work_assignment_id, output_type, status)
                       VALUES (?, ?, 'Not Started')""",
                    (new_id, output_type),
                )
        return new_id

    def update_work_assignment(self, work_assignment_id: int, data: dict[str, Any]) -> bool:
        """
        Update fields on an existing work assignment.

        Only keys present in `data` are updated. Returns True if found and updated.
        """
        updatable = {
            "assignment_number", "assignment_name", "objective_id",
            "operational_period_id", "branch", "division_group", "location",
            "assignment_kind", "priority", "planning_status", "safety_status",
            "resource_status", "description", "tactics_summary", "special_instructions",
            "prepared_by", "approved_by", "updated_by", "notes",
        }
        fields = {k: v for k, v in data.items() if k in updatable}
        if not fields:
            return False
        fields["updated_at"] = _now()
        set_clause = ", ".join(f"{k} = :{k}" for k in fields)
        fields["wa_id"] = work_assignment_id
        with self._connect() as con:
            cur = con.execute(
                f"UPDATE work_assignments SET {set_clause} WHERE id = :wa_id",
                fields,
            )
        return cur.rowcount > 0

    def archive_work_assignment(self, work_assignment_id: int) -> None:
        """Mark a work assignment as archived (soft delete)."""
        with self._connect() as con:
            con.execute(
                "UPDATE work_assignments SET is_archived = 1, updated_at = ? WHERE id = ?",
                (_now(), work_assignment_id),
            )

    def restore_work_assignment(self, work_assignment_id: int) -> None:
        """Restore an archived work assignment."""
        with self._connect() as con:
            con.execute(
                "UPDATE work_assignments SET is_archived = 0, updated_at = ? WHERE id = ?",
                (_now(), work_assignment_id),
            )

    def delete_work_assignment(self, work_assignment_id: int) -> None:
        """
        Permanently delete a work assignment and all related records.

        Prefer archive_work_assignment for normal use. This is irreversible.
        """
        with self._connect() as con:
            con.execute(
                "DELETE FROM work_assignments WHERE id = ?",
                (work_assignment_id,),
            )

    def clone_work_assignment(self, work_assignment_id: int) -> int | None:
        """
        Duplicate an existing work assignment (header only, no linked tasks).

        Returns the new record ID, or None if the source was not found.
        """
        original = self.get_work_assignment(work_assignment_id)
        if not original:
            return None
        d = original.to_db_dict()
        d["assignment_name"] = f"{original.assignment_name} (Copy)"
        d["assignment_number"] = ""
        d["planning_status"] = "Draft"
        return self.create_work_assignment(d)

    # ------------------------------------------------------------------
    # Resource requirement methods
    # ------------------------------------------------------------------

    def list_resource_requirements(self, work_assignment_id: int) -> list[WorkAssignmentResourceRequirement]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM work_assignment_resources WHERE work_assignment_id = ? ORDER BY id",
                (work_assignment_id,),
            ).fetchall()
        return [WorkAssignmentResourceRequirement.from_row(r) for r in rows]

    def add_resource_requirement(self, work_assignment_id: int, data: dict[str, Any]) -> int:
        """Add a resource need line. Returns new row ID."""
        now = _now()
        qty = max(1, int(data.get("quantity_required", 1)))
        with self._connect() as con:
            cur = con.execute(
                """INSERT INTO work_assignment_resources (
                    work_assignment_id, resource_type_id, resource_type_text,
                    capability_id, capability_text, quantity_required,
                    quantity_assigned, quantity_available, quantity_gap,
                    unit, priority, source_note, notes, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,0,0,?,?,?,?,?,?,?)""",
                (
                    work_assignment_id,
                    data.get("resource_type_id"),
                    data.get("resource_type_text", ""),
                    data.get("capability_id"),
                    data.get("capability_text", ""),
                    qty,
                    qty,   # gap = required when newly added
                    data.get("unit", ""),
                    data.get("priority", "Normal"),
                    data.get("source_note", ""),
                    data.get("notes", ""),
                    now, now,
                ),
            )
        return cur.lastrowid

    def update_resource_requirement(self, requirement_id: int, data: dict[str, Any]) -> bool:
        updatable = {
            "resource_type_id", "resource_type_text", "capability_id", "capability_text",
            "quantity_required", "quantity_assigned", "quantity_available", "quantity_gap",
            "unit", "priority", "source_note", "logistics_request_id", "notes",
        }
        fields = {k: v for k, v in data.items() if k in updatable}
        if not fields:
            return False
        fields["updated_at"] = _now()
        fields["rid"] = requirement_id
        set_clause = ", ".join(f"{k} = :{k}" for k in fields if k != "rid")
        with self._connect() as con:
            cur = con.execute(
                f"UPDATE work_assignment_resources SET {set_clause} WHERE id = :rid",
                fields,
            )
        return cur.rowcount > 0

    def remove_resource_requirement(self, requirement_id: int) -> None:
        with self._connect() as con:
            con.execute(
                "DELETE FROM work_assignment_resources WHERE id = ?",
                (requirement_id,),
            )

    def recalculate_resource_gap(self, requirement_id: int) -> None:
        """Recompute quantity_gap = max(required - assigned, 0) for one requirement."""
        with self._connect() as con:
            row = con.execute(
                "SELECT quantity_required, quantity_assigned FROM work_assignment_resources WHERE id = ?",
                (requirement_id,),
            ).fetchone()
            if row:
                gap = max(int(row["quantity_required"]) - int(row["quantity_assigned"]), 0)
                con.execute(
                    "UPDATE work_assignment_resources SET quantity_gap = ?, updated_at = ? WHERE id = ?",
                    (gap, _now(), requirement_id),
                )

    def recalculate_all_resource_gaps(self, work_assignment_id: int) -> None:
        """Recompute gaps for every resource requirement on a work assignment."""
        reqs = self.list_resource_requirements(work_assignment_id)
        for req in reqs:
            if req.id:
                self.recalculate_resource_gap(req.id)

    # ------------------------------------------------------------------
    # Actual resource assignment methods (who is actually assigned)
    # ------------------------------------------------------------------

    def list_assigned_resources(self, requirement_id: int) -> list[WorkAssignmentResourceAssignment]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM work_assignment_resource_assignments WHERE work_assignment_resource_id = ?",
                (requirement_id,),
            ).fetchall()
        return [WorkAssignmentResourceAssignment.from_row(r) for r in rows]

    def assign_actual_resource(
        self,
        requirement_id: int,
        resource_kind: str,
        resource_id: str,
        display_name: str = "",
    ) -> int:
        """Link an actual resource to a requirement line. Returns new row ID."""
        with self._connect() as con:
            cur = con.execute(
                """INSERT INTO work_assignment_resource_assignments
                   (work_assignment_resource_id, resource_kind, resource_id, display_name, status, assigned_at)
                   VALUES (?, ?, ?, ?, 'Planned', ?)""",
                (requirement_id, resource_kind, str(resource_id), display_name, _now()),
            )
            new_id = cur.lastrowid
        # Sync assigned count on the requirement
        self._sync_assigned_count(requirement_id)
        self.recalculate_resource_gap(requirement_id)
        return new_id

    def remove_actual_resource(self, assignment_id: int) -> None:
        with self._connect() as con:
            row = con.execute(
                "SELECT work_assignment_resource_id FROM work_assignment_resource_assignments WHERE id = ?",
                (assignment_id,),
            ).fetchone()
            req_id = row["work_assignment_resource_id"] if row else None
            con.execute(
                "DELETE FROM work_assignment_resource_assignments WHERE id = ?",
                (assignment_id,),
            )
        if req_id:
            self._sync_assigned_count(req_id)
            self.recalculate_resource_gap(req_id)

    def update_actual_resource_status(self, assignment_id: int, status: str) -> None:
        with self._connect() as con:
            con.execute(
                "UPDATE work_assignment_resource_assignments SET status = ? WHERE id = ?",
                (status, assignment_id),
            )

    def _sync_assigned_count(self, requirement_id: int) -> None:
        """Update quantity_assigned to match the count of actual linked resources."""
        with self._connect() as con:
            row = con.execute(
                "SELECT COUNT(*) as cnt FROM work_assignment_resource_assignments WHERE work_assignment_resource_id = ?",
                (requirement_id,),
            ).fetchone()
            count = int(row["cnt"]) if row else 0
            con.execute(
                "UPDATE work_assignment_resources SET quantity_assigned = ?, updated_at = ? WHERE id = ?",
                (count, _now(), requirement_id),
            )

    # ------------------------------------------------------------------
    # Hazard methods
    # ------------------------------------------------------------------

    def list_hazards(self, work_assignment_id: int) -> list[WorkAssignmentHazard]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM work_assignment_hazards WHERE work_assignment_id = ? ORDER BY id",
                (work_assignment_id,),
            ).fetchall()
        return [WorkAssignmentHazard.from_row(r) for r in rows]

    def add_hazard(self, work_assignment_id: int, data: dict[str, Any]) -> int:
        now = _now()
        with self._connect() as con:
            cur = con.execute(
                """INSERT INTO work_assignment_hazards (
                    work_assignment_id, hazard_type_id, hazard_type_text,
                    category, risk_level, likelihood, severity,
                    control_measure, mitigation_text, ppe_text, safety_message,
                    source, is_resolved, notes, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0,?,?,?)""",
                (
                    work_assignment_id,
                    data.get("hazard_type_id"),
                    data.get("hazard_type_text", ""),
                    data.get("category", ""),
                    data.get("risk_level", "Unknown"),
                    data.get("likelihood", "Unknown"),
                    data.get("severity", "Unknown"),
                    data.get("control_measure", ""),
                    data.get("mitigation_text", ""),
                    data.get("ppe_text", ""),
                    data.get("safety_message", ""),
                    data.get("source", ""),
                    data.get("notes", ""),
                    now, now,
                ),
            )
        return cur.lastrowid

    def update_hazard(self, hazard_id: int, data: dict[str, Any]) -> bool:
        updatable = {
            "hazard_type_id", "hazard_type_text", "category", "risk_level",
            "likelihood", "severity", "control_measure", "mitigation_text",
            "ppe_text", "safety_message", "source", "is_resolved", "notes",
        }
        fields = {k: v for k, v in data.items() if k in updatable}
        if not fields:
            return False
        fields["updated_at"] = _now()
        fields["hid"] = hazard_id
        set_clause = ", ".join(f"{k} = :{k}" for k in fields if k != "hid")
        with self._connect() as con:
            cur = con.execute(
                f"UPDATE work_assignment_hazards SET {set_clause} WHERE id = :hid",
                fields,
            )
        return cur.rowcount > 0

    def remove_hazard(self, hazard_id: int) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM work_assignment_hazards WHERE id = ?", (hazard_id,))

    def mark_hazard_resolved(self, hazard_id: int, resolved: bool = True) -> None:
        val = 1 if resolved else 0
        with self._connect() as con:
            con.execute(
                "UPDATE work_assignment_hazards SET is_resolved = ?, updated_at = ? WHERE id = ?",
                (val, _now(), hazard_id),
            )

    # ------------------------------------------------------------------
    # Communications methods
    # ------------------------------------------------------------------

    def list_comms(self, work_assignment_id: int) -> list[WorkAssignmentComms]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM work_assignment_comms WHERE work_assignment_id = ? ORDER BY is_primary DESC, id",
                (work_assignment_id,),
            ).fetchall()
        return [WorkAssignmentComms.from_row(r) for r in rows]

    def add_comms_channel(self, work_assignment_id: int, data: dict[str, Any]) -> int:
        now = _now()
        with self._connect() as con:
            cur = con.execute(
                """INSERT INTO work_assignment_comms (
                    work_assignment_id, channel_id, channel_name, function,
                    zone, channel_number, rx_freq, rx_tone, tx_freq, tx_tone,
                    mode, remarks, is_primary, notes, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    work_assignment_id,
                    data.get("channel_id"),
                    data.get("channel_name", ""),
                    data.get("function", ""),
                    data.get("zone", ""),
                    data.get("channel_number", ""),
                    data.get("rx_freq", ""),
                    data.get("rx_tone", ""),
                    data.get("tx_freq", ""),
                    data.get("tx_tone", ""),
                    data.get("mode", ""),
                    data.get("remarks", ""),
                    1 if data.get("is_primary") else 0,
                    data.get("notes", ""),
                    now, now,
                ),
            )
        return cur.lastrowid

    def update_comms_channel(self, comms_id: int, data: dict[str, Any]) -> bool:
        updatable = {
            "channel_name", "function", "zone", "channel_number",
            "rx_freq", "rx_tone", "tx_freq", "tx_tone", "mode",
            "remarks", "is_primary", "notes",
        }
        fields = {k: v for k, v in data.items() if k in updatable}
        if not fields:
            return False
        fields["updated_at"] = _now()
        fields["cid"] = comms_id
        set_clause = ", ".join(f"{k} = :{k}" for k in fields)
        with self._connect() as con:
            cur = con.execute(
                f"UPDATE work_assignment_comms SET {set_clause} WHERE id = :cid",
                fields,
            )
        return cur.rowcount > 0

    def remove_comms_channel(self, comms_id: int) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM work_assignment_comms WHERE id = ?", (comms_id,))

    # ------------------------------------------------------------------
    # Task link methods
    # ------------------------------------------------------------------

    def list_linked_tasks(self, work_assignment_id: int) -> list[WorkAssignmentTaskLink]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM work_assignment_tasks WHERE work_assignment_id = ? ORDER BY created_at",
                (work_assignment_id,),
            ).fetchall()
        return [WorkAssignmentTaskLink.from_row(r) for r in rows]

    def link_existing_task(
        self,
        work_assignment_id: int,
        task_id: int,
        link_type: str = "Linked Existing",
        notes: str = "",
    ) -> int | None:
        """
        Link an existing Operations task. Rejects duplicate links.
        Returns new link row ID, or None if already linked.
        """
        with self._connect() as con:
            existing = con.execute(
                "SELECT id FROM work_assignment_tasks WHERE work_assignment_id = ? AND task_id = ?",
                (work_assignment_id, task_id),
            ).fetchone()
            if existing:
                return None
            cur = con.execute(
                """INSERT INTO work_assignment_tasks
                   (work_assignment_id, task_id, link_type, created_at, notes)
                   VALUES (?, ?, ?, ?, ?)""",
                (work_assignment_id, int(task_id), link_type, _now(), notes),
            )
        return cur.lastrowid

    def unlink_task(self, link_id: int) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM work_assignment_tasks WHERE id = ?", (link_id,))

    def list_strategies_for_task(self, task_id: int) -> list[dict]:
        """Return all work assignments (strategies) linked to a given task_id."""
        with self._connect() as con:
            rows = con.execute(
                """SELECT wa.id, wa.assignment_number, wa.assignment_name,
                          wa.planning_status, wat.id AS link_id, wat.link_type
                   FROM work_assignment_tasks wat
                   JOIN work_assignments wa ON wa.id = wat.work_assignment_id
                   WHERE wat.task_id = ?
                   ORDER BY wa.assignment_number""",
                (int(task_id),),
            ).fetchall()
        return [dict(r) for r in rows]

    def create_task_from_work_assignment(
        self,
        work_assignment_id: int,
        task_payload: dict[str, Any] | None = None,
    ) -> int | None:
        """
        Create a new Operations task pre-filled from this work assignment.

        Uses the existing Taskings repository if available.
        Returns the new task DB ID, or None if task creation is unavailable.
        """
        wa = self.get_work_assignment(work_assignment_id)
        if not wa:
            return None
        try:
            from modules.operations.taskings.repository import create_task  # type: ignore
        except ImportError:
            # Taskings module not available — caller should show a user message
            return None

        payload = task_payload or {}
        title = payload.get("title") or wa.assignment_name
        description_parts = []
        if wa.description:
            description_parts.append(wa.description)
        if wa.tactics_summary:
            description_parts.append(f"Tactics: {wa.tactics_summary}")
        if wa.special_instructions:
            description_parts.append(f"Special Instructions: {wa.special_instructions}")

        try:
            new_task_id = create_task(
                title=title,
                description="\n".join(description_parts) or None,
                priority=wa.priority,
                location=wa.location or None,
            )
        except Exception:
            return None

        if new_task_id:
            self.link_existing_task(work_assignment_id, new_task_id, link_type="Generated")
        return new_task_id

    # ------------------------------------------------------------------
    # Log methods
    # ------------------------------------------------------------------

    def list_log_entries(self, work_assignment_id: int) -> list[WorkAssignmentLogEntry]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM work_assignment_log WHERE work_assignment_id = ? ORDER BY timestamp DESC",
                (work_assignment_id,),
            ).fetchall()
        return [WorkAssignmentLogEntry.from_row(r) for r in rows]

    def add_log_entry(
        self,
        work_assignment_id: int,
        entry_text: str,
        entry_type: str = "Note",
        critical: bool = False,
    ) -> int:
        with self._connect() as con:
            cur = con.execute(
                """INSERT INTO work_assignment_log
                   (work_assignment_id, timestamp, entry_type, entry_text, critical)
                   VALUES (?, ?, ?, ?, ?)""",
                (work_assignment_id, _now(), entry_type, entry_text, 1 if critical else 0),
            )
        return cur.lastrowid

    def update_log_entry(self, log_id: int, data: dict[str, Any]) -> bool:
        fields: dict[str, Any] = {}
        for key in ("entry_text", "entry_type", "critical"):
            if key in data:
                fields[key] = data[key]
        if not fields:
            return False
        fields["lid"] = log_id
        set_clause = ", ".join(f"{k} = :{k}" for k in fields if k != "lid")
        with self._connect() as con:
            cur = con.execute(
                f"UPDATE work_assignment_log SET {set_clause} WHERE id = :lid",
                fields,
            )
        return cur.rowcount > 0

    def remove_log_entry(self, log_id: int) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM work_assignment_log WHERE id = ?", (log_id,))

    # ------------------------------------------------------------------
    # Output status methods
    # ------------------------------------------------------------------

    def list_outputs(self, work_assignment_id: int) -> list[WorkAssignmentOutputStatus]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM work_assignment_outputs WHERE work_assignment_id = ? ORDER BY output_type",
                (work_assignment_id,),
            ).fetchall()
        return [WorkAssignmentOutputStatus.from_row(r) for r in rows]

    def update_output_status(
        self,
        work_assignment_id: int,
        output_type: str,
        status: str,
        notes: str = "",
    ) -> None:
        """Upsert the output readiness row for a given output type."""
        now = _now()
        with self._connect() as con:
            existing = con.execute(
                "SELECT id FROM work_assignment_outputs WHERE work_assignment_id = ? AND output_type = ?",
                (work_assignment_id, output_type),
            ).fetchone()
            if existing:
                con.execute(
                    "UPDATE work_assignment_outputs SET status = ?, notes = ? WHERE id = ?",
                    (status, notes, existing["id"]),
                )
            else:
                con.execute(
                    """INSERT INTO work_assignment_outputs
                       (work_assignment_id, output_type, status, notes)
                       VALUES (?, ?, ?, ?)""",
                    (work_assignment_id, output_type, status, notes),
                )

    # ------------------------------------------------------------------
    # Status board helper
    # ------------------------------------------------------------------

    def list_work_assignment_status_rows(self) -> list[dict[str, Any]]:
        """
        Return lightweight summary rows suitable for a dashboard/status board.

        Each dict includes: id, assignment_number, assignment_name,
        planning_status, resource_status, safety_status.
        Extend this as the status board API becomes clearer.
        """
        with self._connect() as con:
            rows = con.execute(
                """SELECT id, assignment_number, assignment_name,
                          planning_status, resource_status, safety_status
                   FROM work_assignments
                   WHERE is_archived = 0
                   ORDER BY updated_at DESC"""
            ).fetchall()
        return [dict(r) for r in rows]
