"""Placeholder database schema creation functions.

The real application will eventually contain rich table definitions.
For this kata we keep the schemas minimal and create them on demand.
The functions below are idempotent and may be called multiple times.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

# SQL fragments for master tables
_MASTER_TABLES = {
    "personnel": """
        CREATE TABLE IF NOT EXISTS personnel_master (
            id TEXT PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            callsign TEXT,
            role TEXT,
            status TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """,
    "equipment": """
        CREATE TABLE IF NOT EXISTS equipment_master (
            id TEXT PRIMARY KEY,
            name TEXT,
            type TEXT,
            status TEXT,
            assigned_to TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """,
    "vehicle": """
        CREATE TABLE IF NOT EXISTS vehicle_master (
            id TEXT PRIMARY KEY,
            name TEXT,
            type TEXT,
            status TEXT,
            callsign TEXT,
            assigned_to TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """,
    "aircraft": """
        CREATE TABLE IF NOT EXISTS aircraft_master (
            id TEXT PRIMARY KEY,
            tail_number TEXT,
            type TEXT,
            status TEXT,
            callsign TEXT,
            assigned_to TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """,
}

# SQL fragments for incident tables
_INCIDENT_TABLES = {
    "personnel": """
        CREATE TABLE IF NOT EXISTS personnel_incident (
            id TEXT PRIMARY KEY,
            incident_id TEXT,
            first_name TEXT,
            last_name TEXT,
            callsign TEXT,
            role TEXT,
            status TEXT,
            checked_in_at TEXT,
            updated_at TEXT
        )
    """,
    "equipment": """
        CREATE TABLE IF NOT EXISTS equipment_incident (
            id TEXT PRIMARY KEY,
            incident_id TEXT,
            name TEXT,
            type TEXT,
            status TEXT,
            assigned_to TEXT,
            checked_in_at TEXT,
            updated_at TEXT
        )
    """,
    "vehicle": """
        CREATE TABLE IF NOT EXISTS vehicle_incident (
            id TEXT PRIMARY KEY,
            incident_id TEXT,
            name TEXT,
            type TEXT,
            status TEXT,
            callsign TEXT,
            assigned_to TEXT,
            checked_in_at TEXT,
            updated_at TEXT
        )
    """,
    "aircraft": """
        CREATE TABLE IF NOT EXISTS aircraft_incident (
            id TEXT PRIMARY KEY,
            incident_id TEXT,
            tail_number TEXT,
            type TEXT,
            status TEXT,
            callsign TEXT,
            assigned_to TEXT,
            checked_in_at TEXT,
            updated_at TEXT
        )
    """,
}


def ensure_master_tables_exist(conn: sqlite3.Connection) -> None:
    """Create placeholder master tables if they do not exist."""
    cur = conn.cursor()
    for ddl in _MASTER_TABLES.values():
        cur.execute(ddl)
    conn.commit()


def ensure_incident_tables_exist(conn: sqlite3.Connection) -> None:
    """Create placeholder incident tables if they do not exist."""
    cur = conn.cursor()
    for ddl in _INCIDENT_TABLES.values():
        cur.execute(ddl)
    conn.commit()
