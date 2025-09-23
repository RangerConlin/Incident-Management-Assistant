from __future__ import annotations

"""SQLite helpers for the ICS-203 command module."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator, Set


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


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    )
    return cur.fetchone() is not None


def _column_names(conn: sqlite3.Connection, table: str) -> Set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def _rename_table(conn: sqlite3.Connection, old: str, new: str) -> None:
    conn.execute(f"ALTER TABLE {old} RENAME TO {new}")


def _columns_match(conn: sqlite3.Connection, table: str, expected: Iterable[str]) -> bool:
    existing = _column_names(conn, table)
    return set(expected).issubset(existing)


def _migrate_legacy_tables(conn: sqlite3.Connection) -> None:
    """Rename legacy ICS-203 tables that previously used shared names."""

    legacy_tables = {
        "org_units": {
            "columns": {"unit_type", "parent_unit_id", "sort_order"},
            "target": "ics203_units",
        },
        "org_positions": {
            "columns": {"title", "unit_id", "sort_order"},
            "target": "ics203_positions",
        },
        "org_assignments": {
            "columns": {"position_id", "display_name", "callsign"},
            "target": "ics203_assignments",
        },
        "org_agency_reps": {
            "columns": {"agency", "phone", "email"},
            "target": "ics203_agency_reps",
        },
        "org_versions": {
            "columns": {"label", "created_utc"},
            "target": "ics203_versions",
        },
    }

    for name, meta in legacy_tables.items():
        target = meta["target"]
        if _table_exists(conn, target) or not _table_exists(conn, name):
            continue
        if _columns_match(conn, name, meta["columns"]):
            _rename_table(conn, name, target)


def ensure_incident_schema(incident_id: str | int) -> None:
    """Ensure the ICS-203 tables exist for ``incident_id``."""

    with get_incident_connection(incident_id) as conn:
        _migrate_legacy_tables(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ics203_units (
                id INTEGER PRIMARY KEY,
                incident_id TEXT NOT NULL,
                unit_type TEXT NOT NULL,
                name TEXT NOT NULL,
                parent_unit_id INTEGER,
                sort_order INTEGER NOT NULL DEFAULT 0,
                UNIQUE(incident_id, unit_type, name),
                FOREIGN KEY(parent_unit_id) REFERENCES ics203_units(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ics203_units_incident ON ics203_units(incident_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ics203_units_parent ON ics203_units(parent_unit_id)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ics203_positions (
                id INTEGER PRIMARY KEY,
                incident_id TEXT NOT NULL,
                title TEXT NOT NULL,
                unit_id INTEGER,
                sort_order INTEGER NOT NULL DEFAULT 0,
                UNIQUE(incident_id, title, unit_id),
                FOREIGN KEY(unit_id) REFERENCES ics203_units(id) ON DELETE SET NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ics203_positions_incident ON ics203_positions(incident_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ics203_positions_unit ON ics203_positions(unit_id)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ics203_assignments (
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
                FOREIGN KEY(position_id) REFERENCES ics203_positions(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ics203_assignments_position ON ics203_assignments(position_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ics203_assignments_incident ON ics203_assignments(incident_id)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ics203_agency_reps (
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
            "CREATE INDEX IF NOT EXISTS idx_ics203_agency_reps_incident ON ics203_agency_reps(incident_id)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ics203_versions (
                id INTEGER PRIMARY KEY,
                incident_id TEXT NOT NULL,
                label TEXT NOT NULL,
                created_utc TEXT NOT NULL,
                notes TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ics203_versions_incident ON ics203_versions(incident_id)"
        )
        conn.commit()
