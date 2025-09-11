"""SQLite table schemas for the logistics module."""
from __future__ import annotations

INCIDENT_SCHEMAS = [
    # Personnel table
    """
    CREATE TABLE IF NOT EXISTS personnel (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        callsign TEXT NOT NULL,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        role TEXT NOT NULL,
        team_id INTEGER,
        phone TEXT NOT NULL,
        status TEXT NOT NULL,
        checkin_status TEXT NOT NULL,
        notes TEXT DEFAULT '',
        updated_at INTEGER
    )
    """,
    # Check-ins table
    """
    CREATE TABLE IF NOT EXISTS checkins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        personnel_id INTEGER NOT NULL,
        incident_id TEXT NOT NULL,
        checkin_status TEXT NOT NULL,
        when_ts REAL NOT NULL,
        who TEXT,
        where TEXT,
        notes TEXT,
        FOREIGN KEY(personnel_id) REFERENCES personnel(id)
    )
    """,
    # Equipment table
    """
    CREATE TABLE IF NOT EXISTS equipment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        serial TEXT,
        assigned_team_id INTEGER,
        status TEXT NOT NULL,
        notes TEXT DEFAULT '',
        updated_at INTEGER
    )
    """,
    # Vehicles table
    """
    CREATE TABLE IF NOT EXISTS vehicles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        callsign TEXT,
        assigned_team_id INTEGER,
        status TEXT NOT NULL,
        notes TEXT DEFAULT '',
        updated_at INTEGER
    )
    """,
    # Aircraft table
    """
    CREATE TABLE IF NOT EXISTS aircraft (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tail TEXT NOT NULL,
        type TEXT NOT NULL,
        callsign TEXT,
        assigned_team_id INTEGER,
        status TEXT NOT NULL,
        notes TEXT DEFAULT '',
        updated_at INTEGER
    )
    """,
    # Audit log
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor TEXT,
        action TEXT,
        target_table TEXT,
        target_id INTEGER,
        before_json TEXT,
        after_json TEXT,
        ts INTEGER
    )
    """,
]
