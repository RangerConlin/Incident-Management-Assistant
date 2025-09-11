"""SQLite table definitions for the Logistics module.

The :func:`ensure_incident_schema` helper creates all required tables for a
specific incident database.  It is safe to call repeatedly; missing tables will
be created while existing ones are left untouched.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

PERSONNEL_TABLE = """
CREATE TABLE IF NOT EXISTS personnel (
    id INTEGER PRIMARY KEY,
    callsign TEXT NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    role TEXT NOT NULL,
    team_id INTEGER,
    phone TEXT,
    status TEXT NOT NULL,
    checkin_status TEXT NOT NULL,
    notes TEXT,
    updated_at REAL DEFAULT (strftime('%s','now'))
);
"""

CHECKINS_TABLE = """
CREATE TABLE IF NOT EXISTS checkins (
    id INTEGER PRIMARY KEY,
    personnel_id INTEGER NOT NULL,
    incident_id TEXT NOT NULL,
    checkin_status TEXT NOT NULL,
    when_ts REAL NOT NULL,
    who TEXT,
    where TEXT,
    notes TEXT
);
"""

EQUIPMENT_TABLE = """
CREATE TABLE IF NOT EXISTS equipment (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    serial TEXT,
    assigned_team_id INTEGER,
    status TEXT NOT NULL,
    notes TEXT,
    updated_at REAL DEFAULT (strftime('%s','now'))
);
"""

VEHICLES_TABLE = """
CREATE TABLE IF NOT EXISTS vehicles (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    callsign TEXT,
    assigned_team_id INTEGER,
    status TEXT NOT NULL,
    notes TEXT,
    updated_at REAL DEFAULT (strftime('%s','now'))
);
"""

AIRCRAFT_TABLE = """
CREATE TABLE IF NOT EXISTS aircraft (
    id INTEGER PRIMARY KEY,
    tail TEXT NOT NULL,
    type TEXT NOT NULL,
    callsign TEXT,
    assigned_team_id INTEGER,
    status TEXT NOT NULL,
    notes TEXT,
    updated_at REAL DEFAULT (strftime('%s','now'))
);
"""

AUDIT_TABLE = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    target_table TEXT NOT NULL,
    target_id INTEGER,
    before_json TEXT,
    after_json TEXT,
    ts REAL DEFAULT (strftime('%s','now'))
);
"""


def ensure_incident_schema(db_path: Path | str) -> None:
    """Ensure all required tables exist for ``db_path``.

    Args:
        db_path: Path to the SQLite database file.
    """

    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        cur = conn.cursor()
        for ddl in _incident_ddls():
            cur.executescript(ddl)
        conn.commit()


def _incident_ddls() -> Iterable[str]:
    return [
        PERSONNEL_TABLE,
        CHECKINS_TABLE,
        EQUIPMENT_TABLE,
        VEHICLES_TABLE,
        AIRCRAFT_TABLE,
        AUDIT_TABLE,
    ]
