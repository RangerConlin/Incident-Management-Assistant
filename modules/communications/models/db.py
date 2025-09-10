from __future__ import annotations

"""Database helpers for the communications module.

This module centralises access to the master channel catalog and the
incident specific communications plan.  All functions return SQLite
``Connection`` objects with ``row_factory`` configured to ``sqlite3.Row``
so rows may be treated as dictionaries.

The incident database path is resolved via :mod:`utils.mission_db` to
avoid hard coding any file system locations.
"""

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Iterator

from utils import mission_db

MASTER_DB_PATH = Path("data") / "master.db"


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _conn(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def get_master_conn() -> sqlite3.Connection:
    """Return a connection to the read-only master database."""
    return _conn(MASTER_DB_PATH)


def get_incident_conn(incident_number: str | int) -> sqlite3.Connection:
    """Return a connection to the current incident database."""
    path = mission_db.get_incident_db_path(incident_number)
    return _conn(path)


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def verify_master_access() -> bool:
    """Return ``True`` if the master database is reachable."""
    try:
        with get_master_conn() as c:
            c.execute("SELECT 1 FROM comms_resources LIMIT 1")
        return True
    except Exception:
        return False


def ensure_incident_schema(incident_number: str | int) -> None:
    """Ensure the ``incident_channels`` table exists for ``incident_number``."""
    with get_incident_conn(incident_number) as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS incident_channels (
                id INTEGER PRIMARY KEY,
                master_id INTEGER,
                channel TEXT NOT NULL,
                function TEXT NOT NULL,
                band TEXT NOT NULL,
                system TEXT,
                mode TEXT NOT NULL,
                rx_freq REAL NOT NULL,
                tx_freq REAL,
                rx_tone TEXT,
                tx_tone TEXT,
                squelch_type TEXT,
                squelch_value TEXT,
                repeater INTEGER NOT NULL DEFAULT 0,
                offset REAL,
                encryption TEXT DEFAULT 'None',
                assignment_division TEXT,
                assignment_team TEXT,
                priority TEXT DEFAULT 'Normal',
                include_on_205 INTEGER NOT NULL DEFAULT 1,
                remarks TEXT,
                sort_index INTEGER NOT NULL DEFAULT 1000,
                line_a INTEGER DEFAULT 0,
                line_c INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        # Helpful indexes ---------------------------------------------------
        c.execute("CREATE INDEX IF NOT EXISTS idx_ic_function ON incident_channels(function)")
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_ic_assign ON incident_channels(assignment_division, assignment_team)"
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_ic_band_mode ON incident_channels(band, mode)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ic_rx ON incident_channels(rx_freq)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ic_tx ON incident_channels(tx_freq)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ic_sort ON incident_channels(sort_index)")


# Context managers -----------------------------------------------------------

@contextmanager
def master_cursor() -> Iterator[sqlite3.Cursor]:
    with get_master_conn() as c:
        yield c.cursor()


@contextmanager
def incident_cursor(incident_number: str | int) -> Iterator[sqlite3.Cursor]:
    with get_incident_conn(incident_number) as c:
        yield c.cursor()
