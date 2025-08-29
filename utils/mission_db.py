"""Utilities for mission-specific SQLite databases.

The schema is intentionally left as a placeholder. Future work will
replace the `_placeholder` table with real mission tables.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

BASE_DIR = Path("data") / "missions"


def create_mission_db(slug: str) -> Path:
    """Create a mission database for *slug* and return its path.

    Parameters
    ----------
    slug:
        Filesystem-friendly identifier used for the mission folder.
    """
    mission_dir = BASE_DIR / slug
    mission_dir.mkdir(parents=True, exist_ok=True)
    db_path = mission_dir / "mission.db"
    _initialize(db_path)
    return db_path


def _initialize(db_path: Path) -> None:
    """Initialize the mission database with placeholder schema."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """CREATE TABLE IF NOT EXISTS _placeholder (
            id INTEGER PRIMARY KEY
        )"""
        )
        # TODO: Replace _placeholder table with full mission schema
        conn.commit()
    finally:
        conn.close()


__all__ = ["create_mission_db"]
