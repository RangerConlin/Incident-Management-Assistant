"""Database helpers for the Forms Creator module.

The application stores persistent state in two different SQLite
structures:

* ``data/master.db`` — contains template definitions shared across all
  incidents.
* ``data/incidents/{incident_id}.db`` — contains per-incident form
  instances and user-entered values.

This module exposes a small utility layer that is intentionally light
weight while still encapsulating the boilerplate for working with the
SQLite JSON1 extension and ensuring that schema migrations are applied.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
import json
import sqlite3
from pathlib import Path
from typing import Any, Callable, Generator, Iterable

MASTER_DB_NAME = "master.db"
INCIDENTS_DIR_NAME = "incidents"
TEMPLATES_DIR_NAME = "forms/templates"


def _find_project_root() -> Path:
    """Best-effort discovery of the repository root.

    The helper walks up the directory hierarchy from the current file
    until a directory containing the ``data`` folder is located.  This
    keeps the module resilient to the package being imported from a
    frozen executable or an embedded Python environment.
    """

    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "data").exists():
            return parent
    # Fall back to the directory containing this file.
    return current.parent


PROJECT_ROOT = _find_project_root()
DATA_DIR = PROJECT_ROOT / "data"
MASTER_DB_PATH = DATA_DIR / MASTER_DB_NAME
INCIDENTS_ROOT = DATA_DIR / INCIDENTS_DIR_NAME
TEMPLATES_ROOT = DATA_DIR / TEMPLATES_DIR_NAME


def ensure_data_directories() -> None:
    """Ensure that the expected directory structure is present."""

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    INCIDENTS_ROOT.mkdir(parents=True, exist_ok=True)
    TEMPLATES_ROOT.mkdir(parents=True, exist_ok=True)


def _apply_pragmas(connection: sqlite3.Connection) -> None:
    """Apply SQLite pragmas for better reliability."""

    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.close()


def _initialise_master_schema(connection: sqlite3.Connection) -> None:
    """Create tables inside the master database if required."""

    cursor = connection.cursor()
    cursor.execute("PRAGMA table_info(form_templates)")
    columns = [row[1] for row in cursor.fetchall()]
    if columns and "name" not in columns:
        cursor.execute("ALTER TABLE form_templates RENAME TO form_templates_legacy")
    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS form_templates (
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
        CREATE INDEX IF NOT EXISTS idx_form_templates_name
          ON form_templates(name);
        CREATE INDEX IF NOT EXISTS idx_form_templates_cat
          ON form_templates(category, subcategory);
        """
    )
    cursor.close()


def _initialise_incident_schema(connection: sqlite3.Connection) -> None:
    """Create tables inside an incident database if required."""

    cursor = connection.cursor()
    cursor.executescript(
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
        CREATE INDEX IF NOT EXISTS idx_instance_values_instance
          ON instance_values(instance_id);
        """
    )
    cursor.close()


@contextmanager
def _connection(path: Path, initializer: Callable[[sqlite3.Connection], None]):
    """Create a SQLite connection and automatically apply the schema."""

    ensure_data_directories()
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    _apply_pragmas(connection)
    initializer(connection)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@contextmanager
def master_connection() -> Generator[sqlite3.Connection, None, None]:
    """Context manager yielding a connection to ``master.db``."""

    with _connection(MASTER_DB_PATH, _initialise_master_schema) as conn:
        yield conn


@contextmanager
def incident_connection(incident_id: str) -> Generator[sqlite3.Connection, None, None]:
    """Context manager yielding a connection to an incident database."""

    safe_id = incident_id.strip().replace("\\", "_").replace("/", "_")
    path = INCIDENTS_ROOT / f"{safe_id}.db"
    with _connection(path, _initialise_incident_schema) as conn:
        yield conn


def serialize(value: Any) -> str:
    """Serialise Python values into JSON strings for persistence."""

    if value is None:
        return "null"
    if isinstance(value, str):
        return value
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, Path):
        return str(value)
    return json.dumps(value)


def deserialize(value: str | bytes | None) -> Any:
    """Best effort JSON deserialisation used when reading values."""

    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    value = value.strip()
    if not value:
        return None
    if value.lower() == "null":
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    """Convert ``sqlite3.Row`` objects into serialisable dictionaries."""

    return [dict(row) for row in rows]

