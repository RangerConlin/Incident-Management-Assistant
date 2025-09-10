from __future__ import annotations

"""Utility helpers for locating incident databases.

This module provides a small shim used by a number of modules to resolve the
path to the incident specific SQLite database.  The implementation mirrors the
behaviour expected by the rest of the application but intentionally contains
very little logic so tests may easily override paths if required.
"""

from pathlib import Path
import os

# Base directory where incident databases are stored.  This mirrors the
# behaviour of :mod:`utils.incident_context` which honours the
# ``CHECKIN_DATA_DIR`` environment variable used during tests.
_DATA_DIR = Path(os.environ.get("CHECKIN_DATA_DIR", "data"))


def get_incident_db_path(incident_number: str | int | None) -> Path:
    """Return the filesystem path for ``incident_number``'s database.

    Parameters
    ----------
    incident_number:
        Identifier for the incident.  ``None`` will raise ``RuntimeError``.

    Returns
    -------
    Path
        Fully qualified path to the incident SQLite database.  The path is not
        created automatically; callers are expected to ensure the file exists
        before attempting to connect.
    """
    if incident_number is None:
        raise RuntimeError("Incident number is required")

    base = _DATA_DIR / "incidents"
    base.mkdir(parents=True, exist_ok=True)
    safe = str(incident_number).strip().replace("/", "-")
    return base / f"{safe}.db"


__all__ = ["get_incident_db_path"]
