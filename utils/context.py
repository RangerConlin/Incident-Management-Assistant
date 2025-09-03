from __future__ import annotations

import sqlite3

from utils.db import get_master_conn, get_incident_conn
from utils.state import AppState


def master_db() -> sqlite3.Connection:
    """Return connection to the persistent master database."""
    return get_master_conn()


def require_incident_db() -> sqlite3.Connection:
    """Return connection to the active incident database or raise."""
    if not AppState.get_active_incident():
        raise RuntimeError("No active incident")
    return get_incident_conn()


__all__ = ["master_db", "require_incident_db"]
