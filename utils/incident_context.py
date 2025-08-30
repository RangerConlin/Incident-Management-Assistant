"""Incident context utilities.

This module stores the identifier for the currently active incident and
exposes helpers to derive the path for the incident-specific database.
It intentionally keeps state in module-level globals so it can be easily
mocked in tests or adjusted by higher level application code.
"""
from __future__ import annotations

from pathlib import Path
import os

# Optional environment variable allowing tests to redirect where data
# files are stored. Defaults to the repository's ``data`` directory.
_DATA_DIR = Path(os.environ.get("CHECKIN_DATA_DIR", "data"))

_active_incident_id: str | None = None


def set_active_incident(incident_id: str) -> None:
    """Set the identifier for the active incident."""
    global _active_incident_id
    _active_incident_id = incident_id


def get_active_incident_id() -> str | None:
    """Return the currently configured incident identifier or ``None``."""
    return _active_incident_id


def get_active_incident_db_path() -> Path:
    """Return the path for the active incident database.

    The path is rooted under ``data/incidents`` (or an overridden data
    directory when running tests). If the incident has not been set a
    ``RuntimeError`` is raised.
    """
    if not _active_incident_id:
        raise RuntimeError("Active incident has not been set")

    base = _DATA_DIR / "incidents"
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{_active_incident_id}.db"


__all__ = [
    "set_active_incident",
    "get_active_incident_id",
    "get_active_incident_db_path",
]

