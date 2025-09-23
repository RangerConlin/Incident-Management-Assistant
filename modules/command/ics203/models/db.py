from __future__ import annotations

"""SQLite helpers for the ICS-203 command module."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def _data_dir() -> Path:
    return Path(os.environ.get("CHECKIN_DATA_DIR", "data"))


def _coerce_incident_id(value: str | int) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError("incident identifier must not be empty")
    return text


def incident_db_path(incident_id: str | int) -> Path:
    """Return the filesystem path for an incident's SQLite database."""

    safe_id = _coerce_incident_id(incident_id).replace("/", "-")
    base = _data_dir() / "incidents"
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{safe_id}.db"


def get_incident_connection(incident_id: str | int) -> sqlite3.Connection:
    """Return an SQLite connection for ``incident_id`` with row factory set."""

    path = incident_db_path(incident_id)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def incident_cursor(incident_id: str | int) -> Iterator[sqlite3.Cursor]:
    with get_incident_connection(incident_id) as conn:
        yield conn.cursor()


def ensure_incident_schema(incident_id: str | int) -> None:
    """Ensure the ICS-203 tables exist for ``incident_id``."""

    with get_incident_connection(incident_id) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS org_units (
                id INTEGER PRIMARY KEY,
                incident_id TEXT NOT NULL,
                unit_type TEXT NOT NULL,
                name TEXT NOT NULL,
                parent_unit_id INTEGER,
                sort_order INTEGER NOT NULL DEFAULT 0,
                UNIQUE(incident_id, unit_type, name),
                FOREIGN KEY(parent_unit_id) REFERENCES org_units(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_org_units_incident ON org_units(incident_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_org_units_parent ON org_units(parent_unit_id)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS org_positions (
                id INTEGER PRIMARY KEY,
                incident_id TEXT NOT NULL,
                title TEXT NOT NULL,
                unit_id INTEGER,
                sort_order INTEGER NOT NULL DEFAULT 0,
                UNIQUE(incident_id, title, unit_id),
                FOREIGN KEY(unit_id) REFERENCES org_units(id) ON DELETE SET NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_org_positions_incident ON org_positions(incident_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_org_positions_unit ON org_positions(unit_id)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS org_assignments (
                id INTEGER PRIMARY KEY,
                incident_id TEXT NOT NULL,
                position_id INTEGER NOT NULL,
                person_id INTEGER,
                display_name TEXT,
                callsign TEXT,
                phone TEXT,
                agency TEXT,
                start_utc TEXT,
                end_utc TEXT,
                notes TEXT,
                FOREIGN KEY(position_id) REFERENCES org_positions(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_org_assignments_position ON org_assignments(position_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_org_assignments_incident ON org_assignments(incident_id)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS org_agency_reps (
                id INTEGER PRIMARY KEY,
                incident_id TEXT NOT NULL,
                name TEXT NOT NULL,
                agency TEXT,
                phone TEXT,
                email TEXT,
                notes TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_org_agency_reps_incident ON org_agency_reps(incident_id)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS org_versions (
                id INTEGER PRIMARY KEY,
                incident_id TEXT NOT NULL,
                label TEXT NOT NULL,
                created_utc TEXT NOT NULL,
                notes TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_org_versions_incident ON org_versions(incident_id)"
        )
        conn.commit()
