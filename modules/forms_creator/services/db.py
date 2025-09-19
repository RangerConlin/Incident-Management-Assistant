"""SQLite helper utilities for the form creator module.

The module exposes convenience functions that return SQLite connections with
consistent pragmas and schema initialisation logic.  All paths are resolved
relative to the repository's ``data`` directory to keep the application
self-contained and offline friendly.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Iterable


DATA_DIR = Path("data")
MASTER_DB_PATH = DATA_DIR / "master.db"
INCIDENTS_DIR = DATA_DIR / "incidents"


def _connect(path: Path) -> sqlite3.Connection:
    """Return a SQLite connection with standard pragmas enabled."""

    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_master_db() -> None:
    """Initialise the master database schema if it does not already exist."""

    with get_master_connection() as conn:
        try:
            conn.executescript(_create_template_sql("form_templates"))
        except sqlite3.OperationalError:
            # Existing projects may already have a legacy table named ``form_templates``.
            # The service layer will detect this situation and fall back to an
            # alternate table name without raising during initialisation.
            pass


def ensure_incident_db(incident_id: str) -> Path:
    """Ensure the database for ``incident_id`` exists and has the proper schema."""

    safe_id = incident_id.strip()
    if not safe_id:
        raise ValueError("incident_id cannot be empty")

    db_path = INCIDENTS_DIR / f"{safe_id}.db"
    with get_incident_connection(safe_id) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS form_instances (
              id INTEGER PRIMARY KEY,
              incident_id TEXT NOT NULL,
              template_id INTEGER NOT NULL,
              template_version INTEGER NOT NULL,
              status TEXT NOT NULL DEFAULT 'draft',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS instance_values (
              id INTEGER PRIMARY KEY,
              instance_id INTEGER NOT NULL,
              field_id INTEGER NOT NULL,
              value TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(instance_id) REFERENCES form_instances(id)
            );
            CREATE INDEX IF NOT EXISTS idx_instance_values_instance ON instance_values(instance_id);
            """
        )
    return db_path


@contextmanager
def get_master_connection() -> Generator[sqlite3.Connection, None, None]:
    """Yield a connection to the master database, ensuring the schema exists."""

    conn = _connect(MASTER_DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_incident_connection(incident_id: str) -> Generator[sqlite3.Connection, None, None]:
    """Yield a connection to the per-incident database."""

    safe_id = incident_id.strip()
    if not safe_id:
        raise ValueError("incident_id cannot be empty")

    conn = _connect(INCIDENTS_DIR / f"{safe_id}.db")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def iter_dict_rows(cursor: sqlite3.Cursor, columns: Iterable[str]) -> list[dict]:
    """Helper that converts a cursor result set to dictionaries."""

    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _create_template_sql(table_name: str) -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          category TEXT,
          subcategory TEXT,
          version INTEGER NOT NULL DEFAULT 1,
          background_path TEXT NOT NULL,
          page_count INTEGER NOT NULL,
          schema_version INTEGER NOT NULL DEFAULT 1,
          fields_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE INDEX IF NOT EXISTS idx_{table_name}_name ON {table_name}(name);
        CREATE INDEX IF NOT EXISTS idx_{table_name}_cat ON {table_name}(category, subcategory);
    """
