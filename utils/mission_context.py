"""Mission context utilities.

This module stores the identifier for the currently active
mission/incident and exposes helpers to derive the path for the
mission specific database.  The module intentionally keeps state in
module level globals so it can be easily mocked in tests or adjusted by
higher level application code.
"""
from __future__ import annotations

from pathlib import Path
import os

# Optional environment variable allowing tests to redirect where data
# files are stored.  Defaults to the repository's ``data`` directory.
_DATA_DIR = Path(os.environ.get("CHECKIN_DATA_DIR", "data"))

_active_mission_id: str | None = None


def set_active_mission(mission_id: str) -> None:
    """Set the identifier for the active mission.

    Parameters
    ----------
    mission_id:
        Identifier for the mission.  This is typically a short string
        or UUID.  No validation is performed here as this module is a
        thin context holder.
    """
    global _active_mission_id
    _active_mission_id = mission_id


def get_active_mission_id() -> str | None:
    """Return the currently configured mission identifier or ``None``."""
    return _active_mission_id


def get_active_mission_db_path() -> Path:
    """Return the path for the active mission database.

    The path is rooted under ``data/missions`` (or an overridden data
    directory when running tests).  If the mission has not been set a
    ``RuntimeError`` is raised.
    """
    if not _active_mission_id:
        raise RuntimeError("Active mission has not been set")

    base = _DATA_DIR / "missions"
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{_active_mission_id}.db"
