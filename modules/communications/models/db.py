from __future__ import annotations

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime

from utils.mission_db import get_incident_db_path

MASTER_DB_PATH = Path('data/master.db')


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def get_master_conn() -> sqlite3.Connection:
    """Return a read-only connection to the master database."""
    return _connect(MASTER_DB_PATH)


def get_incident_conn(incident_number: str | int) -> sqlite3.Connection:
    """Return a connection to the incident database, creating directories
    as needed.  The caller is responsible for ensuring the schema is present."""
    path = get_incident_db_path(incident_number)
    return _connect(path)


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------

def verify_master_access() -> bool:
    """Check that the master database is reachable."""
    try:
        with get_master_conn() as conn:
            conn.execute('SELECT 1 FROM comms_resources LIMIT 1').fetchone()
        return True
    except Exception:
        return False


def ensure_incident_schema(incident_number: str | int) -> None:
    """Ensure the ``incident_channels`` table exists for the incident."""
    with get_incident_conn(incident_number) as conn:
        conn.execute(
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
                line_a INTEGER NOT NULL DEFAULT 0,
                line_c INTEGER NOT NULL DEFAULT 0,
                encryption TEXT DEFAULT 'None',
                assignment_division TEXT,
                assignment_team TEXT,
                priority TEXT DEFAULT 'Normal',
                include_on_205 INTEGER NOT NULL DEFAULT 1,
                remarks TEXT,
                sort_index INTEGER NOT NULL DEFAULT 1000,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        indices = [
            'CREATE INDEX IF NOT EXISTS idx_incident_channels_function ON incident_channels(function)',
            'CREATE INDEX IF NOT EXISTS idx_incident_channels_assignment_division ON incident_channels(assignment_division)',
            'CREATE INDEX IF NOT EXISTS idx_incident_channels_assignment_team ON incident_channels(assignment_team)',
            'CREATE INDEX IF NOT EXISTS idx_incident_channels_band_mode ON incident_channels(band, mode)',
            'CREATE INDEX IF NOT EXISTS idx_incident_channels_rx_freq ON incident_channels(rx_freq)',
            'CREATE INDEX IF NOT EXISTS idx_incident_channels_tx_freq ON incident_channels(tx_freq)',
            'CREATE INDEX IF NOT EXISTS idx_incident_channels_sort_index ON incident_channels(sort_index)',
            'CREATE INDEX IF NOT EXISTS idx_incident_channels_line_a ON incident_channels(line_a)',
            'CREATE INDEX IF NOT EXISTS idx_incident_channels_line_c ON incident_channels(line_c)',
        ]
        for sql in indices:
            conn.execute(sql)
        conn.commit()


@contextmanager
def master_cursor():
    with get_master_conn() as conn:
        yield conn.cursor()


@contextmanager
def incident_cursor(incident_number: str | int):
    with get_incident_conn(incident_number) as conn:
        yield conn.cursor()
        conn.commit()
