"""Light weight SQLite connection helpers.

These functions centralise the logic for creating connections to the
application's databases.  Tests can override the base directory by
setting the ``CHECKIN_DATA_DIR`` environment variable before importing
this module.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from . import mission_context

# Base directory for data storage.  Defaults to ``data`` in the
# repository root but can be overridden for tests by the environment
# variable above.
_DATA_DIR = Path(os.environ.get("CHECKIN_DATA_DIR", "data"))


def _connect(path: Path) -> sqlite3.Connection:
    """Create a SQLite connection with row factory configured."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def get_master_conn() -> sqlite3.Connection:
    """Return a connection to the persistent master database."""
    return _connect(_DATA_DIR / "master.db")


def get_mission_conn() -> sqlite3.Connection:
    """Return a connection to the active mission database."""
    mission_path = mission_context.get_active_mission_db_path()
    return _connect(mission_path)
