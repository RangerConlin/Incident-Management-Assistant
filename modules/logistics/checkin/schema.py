"""SQLite schema helpers for the Logistics Check-In module."""
from __future__ import annotations

import sqlite3

_PERSONNEL_TABLE = """
CREATE TABLE IF NOT EXISTS personnel (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    primary_role TEXT,
    phone TEXT,
    callsign TEXT,
    certifications TEXT,
    home_unit TEXT
)
"""

_CHECKINS_TABLE = """
CREATE TABLE IF NOT EXISTS checkins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL,
    ci_status TEXT NOT NULL,
    personnel_status TEXT NOT NULL,
    arrival_time TEXT NOT NULL,
    location TEXT NOT NULL,
    location_other TEXT,
    shift_start TEXT,
    shift_end TEXT,
    notes TEXT,
    incident_callsign TEXT,
    incident_phone TEXT,
    team_id TEXT,
    role_on_team TEXT,
    operational_period TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(person_id)
)
"""

_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    actor TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL
)
"""

_TEAMS_TABLE = """
CREATE TABLE IF NOT EXISTS teams (
    team_id TEXT PRIMARY KEY,
    name TEXT,
    category TEXT
)
"""

_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_checkins_personnel_status ON checkins(personnel_status)",
    "CREATE INDEX IF NOT EXISTS idx_checkins_ci_status ON checkins(ci_status)",
    "CREATE INDEX IF NOT EXISTS idx_history_person_id ON history(person_id)",
)


def ensure_master_schema(conn: sqlite3.Connection) -> None:
    """Ensure the ``personnel`` table exists in ``master.db``."""
    conn.execute(_PERSONNEL_TABLE)
    conn.commit()


def ensure_incident_schema(conn: sqlite3.Connection) -> None:
    """Ensure incident-scoped tables exist."""
    conn.execute(_CHECKINS_TABLE)
    conn.execute(_HISTORY_TABLE)
    conn.execute(_TEAMS_TABLE)
    for stmt in _INDEXES:
        conn.execute(stmt)
    conn.commit()


__all__ = ["ensure_master_schema", "ensure_incident_schema"]
