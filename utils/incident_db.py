"""Incident SQLite file lifecycle management.

This module manages the per-incident SQLite file on disk — creating it from
the template and validating its schema. It does NOT read or write operational
data; active data now lives in MongoDB.

The only SQLite table still actively read by live app code is `narrative_entries`
(used by bridge/incident_bridge.py for task narrative / ICS 214 entries until
that is migrated to the API).

Active incident ID state lives in utils/incident_context.py.
Use incident_context.get_active_incident_id() / set_active_incident() instead
of importing this module for state purposes.
"""
from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from . import incident_storage

# All operational data is now served by MongoDB.  The SQLite incident.db is
# still created from template.db for the spatial bootstrap and for the IAP
# exporter output path, but no tables are required to be present for the app
# to function.  Leave this set empty; keep the validation call site so it can
# be populated again if a future feature needs a SQLite-only table.
_REQUIRED_INCIDENT_TABLES: set[str] = set()


def get_incident_database_path(incident_number: str) -> Path:
    safe_number = incident_storage.sanitize_incident_name(incident_number, fallback="incident")
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
        raise FileNotFoundError(f"Incident database template was not found: {template}")

    shutil.copy2(template, path)

    try:
        with sqlite3.connect(path) as conn:
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
        _validate_initialized_schema(conn)

    incident_storage.write_incident_manifest(paths, metadata)
    return paths.incident_db


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
    incident_storage.write_incident_manifest(paths, metadata)
    return paths.incident_db
