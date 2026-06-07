"""Shared resource type assignment helpers.

This module keeps the cross-cutting "real resource -> resource type" mapping
logic in one place so personnel, vehicles, equipment, teams, and check-in can
all use the same schema and query behavior.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Optional

from models.database import DB_PATH as DEFAULT_MASTER_DB_PATH
from utils import incident_context

READINESS_STATUSES: tuple[str, ...] = (
    "Ready",
    "Partially Ready",
    "Missing Personnel",
    "Missing Equipment",
    "Out of Service",
    "Unknown",
)


class ResourceAssignmentRepository:
    """Repository for linking live resources to master resource types."""

    def __init__(
        self,
        master_db_path: str | Path | None = None,
        incident_db_path: str | Path | None = None,
    ) -> None:
        self.master_db_path = Path(master_db_path or DEFAULT_MASTER_DB_PATH)
        self.incident_db_path = Path(incident_db_path) if incident_db_path else None
        self.ensure_schema()

    @contextmanager
    def _master_connect(self) -> Iterable[sqlite3.Connection]:
        self.master_db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.master_db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    @contextmanager
    def _incident_connect(self) -> Iterable[sqlite3.Connection]:
        incident_path = self.incident_db_path or Path(incident_context.get_active_incident_db_path())
        incident_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(incident_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def ensure_schema(self) -> None:
        """Create additive mapping tables and columns if they are missing."""

        with self._master_connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS personnel_resource_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    personnel_id TEXT NOT NULL,
                    resource_type_id INTEGER NOT NULL,
                    is_primary INTEGER NOT NULL DEFAULT 0,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(personnel_id, resource_type_id)
                );

                CREATE TABLE IF NOT EXISTS personnel_capabilities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    personnel_id TEXT NOT NULL,
                    capability_id INTEGER NOT NULL,
                    source TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(personnel_id, capability_id)
                );
                """
            )
            self._ensure_columns(
                conn,
                "vehicles",
                {"resource_type_id": "INTEGER"},
            )
            self._ensure_columns(
                conn,
                "equipment",
                {
                    "resource_type_id": "INTEGER",
                    "parent_equipment_id": "INTEGER",
                    "kit_instance_id": "INTEGER",
                    "condition_status": "TEXT",
                    "contents_verified": "INTEGER NOT NULL DEFAULT 0",
                    "team_id": "INTEGER",
                },
            )
            self._ensure_columns(
                conn,
                "personnel",
                {"team_id": "INTEGER"},
            )
            self._backfill_equipment_condition_status(conn)

        try:
            with self._incident_connect() as conn:
                self.ensure_incident_schema(conn)
        except Exception:
            # Team and availability callers often bootstrap before an incident
            # is selected. The master mappings should still remain usable.
            pass

    def ensure_incident_schema(self, conn: sqlite3.Connection) -> None:
        """Apply additive incident-scoped schema updates."""

        self._ensure_columns(
            conn,
            "personnel",
            {
                "team_id": "INTEGER",
                "resource_type_id": "INTEGER",
            },
        )
        self._ensure_columns(
            conn,
            "vehicles",
            {
                "resource_type_id": "INTEGER",
                "team_id": "INTEGER",
            },
        )
        self._ensure_columns(
            conn,
            "equipment",
            {
                "resource_type_id": "INTEGER",
                "parent_equipment_id": "INTEGER",
                "kit_instance_id": "INTEGER",
                "condition_status": "TEXT",
                "contents_verified": "INTEGER NOT NULL DEFAULT 0",
                "team_id": "INTEGER",
            },
        )
        self._ensure_columns(
            conn,
            "teams",
            {
                "resource_type_id": "INTEGER",
                "readiness_status": "TEXT",
            },
        )
        self._backfill_equipment_condition_status(conn)

    def _ensure_columns(
        self,
        conn: sqlite3.Connection,
        table_name: str,
        columns: dict[str, str],
    ) -> None:
        tables = {
            row["name"] if isinstance(row, sqlite3.Row) else row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if table_name not in tables:
            return
        existing = {
            row["name"] if isinstance(row, sqlite3.Row) else row[1]
            for row in conn.execute(f"PRAGMA table_info({table_name})")
        }
        for column_name, ddl in columns.items():
            if column_name not in existing:
                conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")

    def _backfill_equipment_condition_status(self, conn: sqlite3.Connection) -> None:
        columns = {
            row["name"] if isinstance(row, sqlite3.Row) else row[1]
            for row in conn.execute("PRAGMA table_info(equipment)")
        }
        if "condition_status" in columns and "condition" in columns:
            conn.execute(
                """
                UPDATE equipment
                SET condition_status = COALESCE(NULLIF(TRIM(condition_status), ''), condition, 'Unknown')
                WHERE condition_status IS NULL OR TRIM(condition_status) = ''
                """
            )

    # ------------------------------------------------------------------
    # Personnel mappings
    # ------------------------------------------------------------------
    def get_personnel_resource_types(self, personnel_id: str | int) -> list[dict[str, Any]]:
        with self._master_connect() as conn:
            rows = conn.execute(
                """
                SELECT prt.*,
                       rt.name AS resource_type_name,
                       rt.planning_display_name
                FROM personnel_resource_types prt
                LEFT JOIN resource_types rt ON rt.id = prt.resource_type_id
                WHERE prt.personnel_id = ?
                ORDER BY prt.is_primary DESC, lower(COALESCE(rt.planning_display_name, rt.name, ''))
                """,
                (str(personnel_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def set_personnel_resource_types(
        self,
        personnel_id: str | int,
        resource_type_ids: Iterable[int],
        primary_resource_type_id: Optional[int] = None,
        notes_by_resource_type: Optional[dict[int, str]] = None,
    ) -> None:
        unique_ids = [int(value) for value in dict.fromkeys(int(v) for v in resource_type_ids)]
        notes_by_resource_type = notes_by_resource_type or {}
        with self._master_connect() as conn:
            conn.execute(
                "DELETE FROM personnel_resource_types WHERE personnel_id = ?",
                (str(personnel_id),),
            )
            for index, resource_type_id in enumerate(unique_ids):
                is_primary = int(
                    resource_type_id == primary_resource_type_id
                    if primary_resource_type_id is not None
                    else index == 0
                )
                conn.execute(
                    """
                    INSERT INTO personnel_resource_types
                        (personnel_id, resource_type_id, is_primary, notes, created_at, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (
                        str(personnel_id),
                        resource_type_id,
                        is_primary,
                        notes_by_resource_type.get(resource_type_id, ""),
                    ),
                )

    def get_personnel_capabilities(self, personnel_id: str | int) -> list[dict[str, Any]]:
        with self._master_connect() as conn:
            rows = conn.execute(
                """
                SELECT pc.*, rc.name AS capability_name, rc.category AS capability_category
                FROM personnel_capabilities pc
                LEFT JOIN resource_capabilities rc ON rc.id = pc.capability_id
                WHERE pc.personnel_id = ?
                ORDER BY lower(COALESCE(rc.name, ''))
                """,
                (str(personnel_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Simple single-resource mappings
    # ------------------------------------------------------------------
    def get_vehicle_resource_type(self, vehicle_id: str | int) -> Optional[int]:
        return self._get_single_resource_type("vehicles", vehicle_id)

    def set_vehicle_resource_type(self, vehicle_id: str | int, resource_type_id: Optional[int]) -> None:
        self._set_single_resource_type("vehicles", vehicle_id, resource_type_id)

    def get_equipment_resource_type(self, equipment_id: str | int) -> Optional[int]:
        return self._get_single_resource_type("equipment", equipment_id)

    def set_equipment_resource_type(self, equipment_id: str | int, resource_type_id: Optional[int]) -> None:
        self._set_single_resource_type("equipment", equipment_id, resource_type_id)

    def get_team_resource_type(self, team_id: str | int) -> Optional[int]:
        with self._incident_connect() as conn:
            self.ensure_incident_schema(conn)
            row = conn.execute(
                "SELECT resource_type_id FROM teams WHERE id = ?",
                (team_id,),
            ).fetchone()
        return int(row["resource_type_id"]) if row and row["resource_type_id"] not in (None, "") else None

    def set_team_resource_type(self, team_id: str | int, resource_type_id: Optional[int]) -> None:
        with self._incident_connect() as conn:
            self.ensure_incident_schema(conn)
            conn.execute(
                "UPDATE teams SET resource_type_id = ? WHERE id = ?",
                (resource_type_id, team_id),
            )

    def set_team_readiness_status(self, team_id: str | int, readiness_status: Optional[str]) -> None:
        normalized = str(readiness_status or "").strip() or "Unknown"
        with self._incident_connect() as conn:
            self.ensure_incident_schema(conn)
            conn.execute(
                "UPDATE teams SET readiness_status = ? WHERE id = ?",
                (normalized, team_id),
            )

    def _get_single_resource_type(self, table_name: str, record_id: str | int) -> Optional[int]:
        with self._master_connect() as conn:
            row = conn.execute(
                f"SELECT resource_type_id FROM {table_name} WHERE id = ?",
                (record_id,),
            ).fetchone()
        return int(row["resource_type_id"]) if row and row["resource_type_id"] not in (None, "") else None

    def _set_single_resource_type(
        self,
        table_name: str,
        record_id: str | int,
        resource_type_id: Optional[int],
    ) -> None:
        with self._master_connect() as conn:
            conn.execute(
                f"UPDATE {table_name} SET resource_type_id = ? WHERE id = ?",
                (resource_type_id, record_id),
            )

    # ------------------------------------------------------------------
    # Lookup helpers for UI display
    # ------------------------------------------------------------------
    def get_resource_type_name(self, resource_type_id: Optional[int]) -> str:
        if resource_type_id in (None, ""):
            return ""
        with self._master_connect() as conn:
            row = conn.execute(
                """
                SELECT planning_display_name, name
                FROM resource_types
                WHERE id = ?
                """,
                (int(resource_type_id),),
            ).fetchone()
        if not row:
            return ""
        return str(row["planning_display_name"] or row["name"] or "")

    def get_expected_kit_contents(self, resource_type_id: Optional[int]) -> list[dict[str, Any]]:
        if resource_type_id in (None, ""):
            return []
        with self._master_connect() as conn:
            rows = conn.execute(
                """
                SELECT rtc.quantity,
                       rtc.unit,
                       rtc.required,
                       rtc.notes,
                       rt.name AS component_name,
                       rt.category AS component_category
                FROM resource_type_components rtc
                JOIN resource_types rt ON rt.id = rtc.component_resource_type_id
                WHERE rtc.parent_resource_type_id = ?
                ORDER BY lower(rt.name)
                """,
                (int(resource_type_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Availability helpers
    # ------------------------------------------------------------------
    def get_available_resources_by_type(self, resource_type_id: int) -> dict[str, list[dict[str, Any]]]:
        return {
            "personnel": self.get_available_personnel_by_resource_type(resource_type_id),
            "vehicles": self.get_available_vehicles_by_resource_type(resource_type_id),
            "equipment": self.get_available_equipment_by_resource_type(resource_type_id),
            "teams": self.get_available_teams_by_resource_type(resource_type_id),
        }

    def get_available_resources_by_capability(self, capability_id: int) -> dict[str, list[dict[str, Any]]]:
        with self._master_connect() as conn:
            type_ids = [
                int(row["resource_type_id"])
                for row in conn.execute(
                    """
                    SELECT resource_type_id
                    FROM resource_type_capabilities
                    WHERE capability_id = ?
                    """,
                    (int(capability_id),),
                ).fetchall()
            ]
        seen: set[tuple[str, Any]] = set()
        combined = {"personnel": [], "vehicles": [], "equipment": [], "teams": []}
        for resource_type_id in type_ids:
            bucket = self.get_available_resources_by_type(resource_type_id)
            for key, rows in bucket.items():
                for row in rows:
                    marker = (key, row.get("id"))
                    if marker not in seen:
                        seen.add(marker)
                        combined[key].append(row)
        return combined

    def get_available_personnel_by_resource_type(self, resource_type_id: int) -> list[dict[str, Any]]:
        with self._master_connect() as master_conn:
            personnel_links = [
                dict(row)
                for row in master_conn.execute(
                    """
                    SELECT personnel_id, is_primary
                    FROM personnel_resource_types
                    WHERE resource_type_id = ?
                    """,
                    (int(resource_type_id),),
                ).fetchall()
            ]
        if not personnel_links:
            return []
        link_map = {str(row["personnel_id"]): row for row in personnel_links}
        with self._incident_connect() as conn:
            self.ensure_incident_schema(conn)
            checkins_exists = self._table_exists(conn, "checkins")
            columns = self._table_columns(conn, "personnel")
            placeholders = ", ".join("?" for _ in link_map)
            select_parts = [
                "p.id",
                "p.name" if "name" in columns else "NULL AS name",
                "p.callsign" if "callsign" in columns else "NULL AS callsign",
                "p.role" if "role" in columns else "NULL AS role",
                "p.phone" if "phone" in columns else "NULL AS phone",
                "p.team_id" if "team_id" in columns else "NULL AS team_id",
            ]
            sql = f"""
                SELECT {", ".join(select_parts)}
                FROM personnel p
                WHERE CAST(p.id AS TEXT) IN ({placeholders})
            """
            rows = [dict(row) for row in conn.execute(sql, tuple(link_map.keys())).fetchall()]
            for row in rows:
                row["is_primary"] = link_map.get(str(row.get("id")), {}).get("is_primary", 0)
            return [
                row for row in rows
                if self._personnel_is_available(conn, row, checkins_exists)
            ]

    def get_available_vehicles_by_resource_type(self, resource_type_id: int) -> list[dict[str, Any]]:
        with self._incident_connect() as conn:
            self.ensure_incident_schema(conn)
            columns = self._table_columns(conn, "vehicles")
            rows = [
                dict(row)
                for row in conn.execute(
                    f"""
                    SELECT id,
                           {"license_plate" if "license_plate" in columns else "NULL AS license_plate"},
                           {"vin" if "vin" in columns else "NULL AS vin"},
                           {"make" if "make" in columns else "NULL AS make"},
                           {"model" if "model" in columns else "NULL AS model"},
                           {"status_id" if "status_id" in columns else "NULL AS status_id"},
                           {"team_id" if "team_id" in columns else "NULL AS team_id"},
                           {"resource_type_id" if "resource_type_id" in columns else "NULL AS resource_type_id"}
                    FROM vehicles
                    WHERE resource_type_id = ?
                    """,
                    (int(resource_type_id),),
                ).fetchall()
            ]
            return [row for row in rows if self._vehicle_is_available(row)]

    def get_available_equipment_by_resource_type(self, resource_type_id: int) -> list[dict[str, Any]]:
        with self._incident_connect() as conn:
            self.ensure_incident_schema(conn)
            columns = self._table_columns(conn, "equipment")
            rows = [
                dict(row)
                for row in conn.execute(
                    f"""
                    SELECT id,
                           {"name" if "name" in columns else "NULL AS name"},
                           {"type" if "type" in columns else "NULL AS type"},
                           {"condition" if "condition" in columns else "NULL AS condition"},
                           {"condition_status" if "condition_status" in columns else "NULL AS condition_status"},
                           {"team_id" if "team_id" in columns else "NULL AS team_id"},
                           {"resource_type_id" if "resource_type_id" in columns else "NULL AS resource_type_id"},
                           {"contents_verified" if "contents_verified" in columns else "0 AS contents_verified"}
                    FROM equipment
                    WHERE resource_type_id = ?
                    """,
                    (int(resource_type_id),),
                ).fetchall()
            ]
            return [row for row in rows if self._equipment_is_available(row)]

    def get_available_teams_by_resource_type(self, resource_type_id: int) -> list[dict[str, Any]]:
        with self._incident_connect() as conn:
            self.ensure_incident_schema(conn)
            columns = self._table_columns(conn, "teams")
            rows = [
                dict(row)
                for row in conn.execute(
                    f"""
                    SELECT id,
                           {"name" if "name" in columns else "NULL AS name"},
                           {"callsign" if "callsign" in columns else "NULL AS callsign"},
                           {"status" if "status" in columns else "NULL AS status"},
                           {"current_task_id" if "current_task_id" in columns else "NULL AS current_task_id"},
                           {"readiness_status" if "readiness_status" in columns else "NULL AS readiness_status"},
                           {"resource_type_id" if "resource_type_id" in columns else "NULL AS resource_type_id"}
                    FROM teams
                    WHERE resource_type_id = ?
                    """,
                    (int(resource_type_id),),
                ).fetchall()
            ]
            return [row for row in rows if self._team_is_available(row)]

    def _personnel_is_available(
        self,
        conn: sqlite3.Connection,
        row: dict[str, Any],
        checkins_exists: bool,
    ) -> bool:
        if row.get("team_id") not in (None, "", 0, "0"):
            return False
        if not checkins_exists:
            return True
        checkin = conn.execute(
            """
            SELECT ci_status, personnel_status
            FROM checkins
            WHERE person_id = ?
            ORDER BY rowid DESC
            LIMIT 1
            """,
            (str(row.get("id")),),
        ).fetchone()
        if checkin is None:
            return True
        ci_status = str(checkin["ci_status"] or "").strip().lower()
        personnel_status = str(checkin["personnel_status"] or "").strip().lower()
        if ci_status and ci_status not in {"checked in", "checked-in", "active"}:
            return False
        if personnel_status in {"unavailable", "demobilized", "out of service"}:
            return False
        return True

    def _vehicle_is_available(self, row: dict[str, Any]) -> bool:
        if row.get("team_id") not in (None, "", 0, "0"):
            return False
        status = str(row.get("status_id") or "").strip().lower()
        return status not in {"out of service", "retired", "assigned"}

    def _equipment_is_available(self, row: dict[str, Any]) -> bool:
        if row.get("team_id") not in (None, "", 0, "0"):
            return False
        status = str(row.get("condition_status") or row.get("condition") or "").strip().lower()
        return status not in {"out of service", "assigned"}

    def _team_is_available(self, row: dict[str, Any]) -> bool:
        status = str(row.get("status") or "").strip().lower()
        if status in {"out of service", "offline"}:
            return False
        if row.get("current_task_id") not in (None, "", 0, "0"):
            return False
        readiness = str(row.get("readiness_status") or "").strip().lower()
        return readiness not in {"out of service"}

    def _table_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ? LIMIT 1",
            (table_name,),
        ).fetchone()
        return row is not None

    def _table_columns(self, conn: sqlite3.Connection, table_name: str) -> set[str]:
        if not self._table_exists(conn, table_name):
            return set()
        return {
            row["name"] if isinstance(row, sqlite3.Row) else row[1]
            for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
