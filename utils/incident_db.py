from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path
from typing import Optional

from modules.gis.services.schema_bootstrap import ensure_spatial_schema
from . import incident_storage

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


def _sanitize_incident_number(incident_number: str) -> str:
    return incident_storage.sanitize_incident_name(incident_number, fallback="incident")


def get_incident_database_path(incident_number: str) -> Path:
    safe_number = _sanitize_incident_number(incident_number)
    if not safe_number:
        raise ValueError("Incident number is required to create an incident database.")
    resolved = incident_storage.resolve_incident_paths_by_identifier(safe_number)
    if resolved is not None:
        return resolved.incident_db
    metadata = incident_storage.infer_incident_metadata(safe_number)
    paths = incident_storage.get_incident_paths(
        incident_number=metadata.get("incident_number") or safe_number,
        incident_name=metadata.get("name") or safe_number,
        incident_id=metadata.get("incident_id") or safe_number,
    )
    return paths.incident_db


def get_spatial_database_path(incident_number: str) -> Path:
    safe_number = _sanitize_incident_number(incident_number)
    resolved = incident_storage.resolve_incident_paths_by_identifier(safe_number)
    if resolved is not None:
        return resolved.spatial_db
    metadata = incident_storage.infer_incident_metadata(safe_number)
    paths = incident_storage.get_incident_paths(
        incident_number=metadata.get("incident_number") or safe_number,
        incident_name=metadata.get("name") or safe_number,
        incident_id=metadata.get("incident_id") or safe_number,
    )
    return paths.spatial_db


def get_template_database_path() -> Path:
    candidates: list[Path] = []

    explicit = incident_storage.data_root() / "incidents" / "template.db"
    candidates.append(explicit)
    repo_template = Path(__file__).resolve().parents[1] / "data" / "incidents" / "template.db"
    if repo_template not in candidates:
        candidates.append(repo_template)

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    searched = "\n - ".join(str(path) for path in candidates)
    raise FileNotFoundError(
        "Incident database template was not found. "
        "Place template.db in the incident data directory."
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
    ensure_spatial_schema(conn)

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

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS incident_meta (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            icp_address TEXT,
            icp_lat REAL,
            icp_lon REAL,
            updated_at TEXT
        )
        """
    )
    cur = conn.execute("SELECT COUNT(*) FROM incident_meta")
    count = int(cur.fetchone()[0])
    if count == 0:
        conn.execute("INSERT INTO incident_meta (id) VALUES (1)")

    conn.commit()


def _validate_initialized_schema(conn: sqlite3.Connection) -> None:
    missing = sorted(_REQUIRED_INCIDENT_TABLES.difference(_table_names(conn)))
    if missing:
        raise RuntimeError(
            "Incident database initialization failed because required tables are missing: "
            + ", ".join(missing)
        )


def _bootstrap_spatial_database(spatial_path: Path) -> None:
    with sqlite3.connect(spatial_path) as spatial_conn:
        ensure_spatial_schema(spatial_conn)
        spatial_conn.commit()


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
        raise FileNotFoundError(f"Incident database template was not found: {template}")

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
    incident_storage.ensure_layout_initialized()
    metadata = incident_storage.infer_incident_metadata(incident_number)
    paths = incident_storage.resolve_incident_paths_by_identifier(incident_number)
    if paths is None:
        paths = incident_storage.get_incident_paths(
            incident_number=metadata.get("incident_number") or incident_number,
            incident_name=metadata.get("name") or incident_number,
            incident_id=metadata.get("incident_id") or incident_number,
        )
    incident_storage.ensure_incident_structure(paths, metadata)

    if not paths.incident_db.exists() or paths.incident_db.stat().st_size == 0:
        initialize_incident_database(
            paths.incident_db,
            incident_number=incident_number,
            exist_ok=True,
        )

    with sqlite3.connect(paths.incident_db) as conn:
        _ensure_schema_compatibility(conn)
        _validate_initialized_schema(conn)

    _bootstrap_spatial_database(paths.spatial_db)
    incident_storage.write_incident_manifest(paths, metadata)
    return paths.incident_db


def set_active_incident_id(value: object | None) -> None:
    global _active_incident_id
    _active_incident_id = None if value is None else str(value)


def get_active_incident_id() -> Optional[str]:
    return _active_incident_id


def create_incident_database(incident_number: str, *, incident_name: str | None = None) -> Path:
    """Create a fully initialized incident folder and operational database."""
    incident_storage.ensure_layout_initialized()
    metadata = incident_storage.infer_incident_metadata(incident_number)
    if incident_name:
        metadata["name"] = incident_name
    paths = incident_storage.get_incident_paths(
        incident_number=metadata.get("incident_number") or incident_number,
        incident_name=metadata.get("name") or incident_number,
        incident_id=metadata.get("incident_id") or incident_number,
    )
    if paths.incident_db.exists():
        raise FileExistsError(f"Incident database already exists: {paths.incident_db}")

    incident_storage.ensure_incident_structure(paths, metadata)
    initialize_incident_database(paths.incident_db, incident_number=incident_number)
    _bootstrap_spatial_database(paths.spatial_db)
    incident_storage.write_incident_manifest(paths, metadata)
    return paths.incident_db
