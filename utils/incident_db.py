from __future__ import annotations

import os
import shutil
import sqlite3
from pathlib import Path
from typing import Optional

_active_incident_id: Optional[str] = None

_REQUIRED_INCIDENT_TABLES = {
    "agency_contacts",
    "assignment_air",
    "assignment_ground",
    "attachments",
    "audit_logs",
    "debriefs",
    "equipment",
    "narrative_entries",
    "operationalperiods",
    "personnel",
    "planning_logs",
    "planning_notes",
    "task_personnel",
    "task_teams",
    "task_vehicles",
    "tasks",
    "teams",
    "vehicles",
}


def _data_dir() -> Path:
    return Path(os.environ.get("CHECKIN_DATA_DIR", "data"))


def _incidents_dir() -> Path:
    base = _data_dir() / "incidents"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _sanitize_incident_number(incident_number: str) -> str:
    return str(incident_number).strip().replace("/", "-")


def get_incident_database_path(incident_number: str) -> Path:
    safe_number = _sanitize_incident_number(incident_number)
    if not safe_number:
        raise ValueError("Incident number is required to create an incident database.")
    return _incidents_dir() / f"{safe_number}.db"


def get_template_database_path() -> Path:
    candidates: list[Path] = []

    explicit = os.environ.get("INCIDENT_TEMPLATE_DB")
    if explicit:
        candidates.append(Path(explicit))

    data_template = _incidents_dir() / "template.db"
    candidates.append(data_template)

    repo_template = Path(__file__).resolve().parents[1] / "data" / "incidents" / "template.db"
    if repo_template not in candidates:
        candidates.append(repo_template)

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    searched = "\n - ".join(str(path) for path in candidates)
    raise FileNotFoundError(
        "Incident database template was not found. "
        "Place template.db in the incident data directory or set INCIDENT_TEMPLATE_DB."
        f"\nSearched:\n - {searched}"
    )


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {str(row[0]) for row in rows}


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, decl: str) -> None:
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def _ensure_notifications_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER,
            title TEXT,
            message TEXT,
            severity TEXT,
            source TEXT,
            entity_type TEXT,
            entity_id TEXT,
            toast_mode TEXT,
            toast_duration_ms INTEGER
        )
        """
    )
    _ensure_column(conn, "notifications", "toast_mode", "TEXT")
    _ensure_column(conn, "notifications", "toast_duration_ms", "INTEGER")


def _ensure_schema_compatibility(conn: sqlite3.Connection) -> None:
    _ensure_notifications_schema(conn)

    tables = _table_names(conn)
    if "teams" in tables:
        team_columns = {
            "name": "TEXT",
            "status": "TEXT",
            "status_updated": "TEXT",
            "current_task_id": "INTEGER",
            "needs_attention": "BOOLEAN DEFAULT 0",
            "callsign": "TEXT",
            "role": "TEXT",
            "priority": "INTEGER",
            "leader_phone": "TEXT",
            "phone": "TEXT",
            "notes": "TEXT",
            "primary_task": "TEXT",
            "assignment": "TEXT",
            "last_known_lat": "REAL",
            "last_known_lon": "REAL",
            "route": "TEXT",
            "members_json": "TEXT",
            "vehicles_json": "TEXT",
            "equipment_json": "TEXT",
            "aircraft_json": "TEXT",
            "comms_preset_id": "INTEGER",
            "radio_ids": "TEXT",
            "team_type": "TEXT",
            "last_comm_ping": "TEXT",
            "emergency_flag": "BOOLEAN",
            "last_checkin_at": "TEXT",
            "checkin_reference_at": "TEXT",
        }
        for column, decl in team_columns.items():
            _ensure_column(conn, "teams", column, decl)

    if "tasks" in tables:
        task_columns = {
            "category": "TEXT",
            "task_type": "TEXT",
            "assignment": "TEXT",
            "team_leader": "TEXT",
            "team_phone": "TEXT",
        }
        for column, decl in task_columns.items():
            _ensure_column(conn, "tasks", column, decl)

    conn.commit()


def _validate_initialized_schema(conn: sqlite3.Connection) -> None:
    missing = sorted(_REQUIRED_INCIDENT_TABLES.difference(_table_names(conn)))
    if missing:
        raise RuntimeError(
            "Incident database initialization failed because required tables are missing: "
            + ", ".join(missing)
        )


def initialize_incident_database(
    db_path: Path,
    *,
    incident_number: str | None = None,
    template_path: Path | None = None,
    exist_ok: bool = False,
) -> Path:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists() and not exist_ok:
        raise FileExistsError(f"Incident database already exists: {path}")

    if path.exists() and path.stat().st_size == 0:
        path.unlink()

    template = Path(template_path) if template_path is not None else get_template_database_path()
    if not template.is_file():
        raise FileNotFoundError(
            f"Incident database template was not found: {template}"
        )

    shutil.copy2(template, path)

    try:
        with sqlite3.connect(path) as conn:
            _ensure_schema_compatibility(conn)
            _validate_initialized_schema(conn)
    except Exception as exc:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        incident_label = f" for incident '{incident_number}'" if incident_number else ""
        raise RuntimeError(
            "Failed to initialize the incident database"
            f"{incident_label} from template '{template}'."
        ) from exc

    return path


def ensure_incident_database(incident_number: str) -> Path:
    db_path = get_incident_database_path(incident_number)
    if not db_path.exists() or db_path.stat().st_size == 0:
        return initialize_incident_database(
            db_path,
            incident_number=incident_number,
            exist_ok=True,
        )

    with sqlite3.connect(db_path) as conn:
        _ensure_schema_compatibility(conn)
        _validate_initialized_schema(conn)
    return db_path


def set_active_incident_id(value: object | None) -> None:
    """Persist the active incident identifier for SQLite-backed modules.

    Parameters
    ----------
    value:
        Any incident identifier understood by the wider application.  ``None``
        clears the active incident.  Non-``None`` values are coerced to
        ``str`` so callers can pass integers from legacy dialogs without
        performing their own conversion.
    """

    global _active_incident_id
    _active_incident_id = None if value is None else str(value)


def get_active_incident_id() -> Optional[str]:
    return _active_incident_id


def create_incident_database(incident_number: str) -> Path:
    """Create a fully initialized incident database named after the incident number.

    The file is created at ``data/incidents/<incident_number>.db``. The schema is
    initialized by copying the incident template database and applying small
    compatibility adjustments required by the current application code.
    """
    db_path = get_incident_database_path(incident_number)
    return initialize_incident_database(db_path, incident_number=incident_number)
