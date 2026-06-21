"""MongoDB access helpers for the medical module."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def _ensure_sarapp_db_on_path() -> None:
    root = Path(__file__).resolve().parents[3]
    package_root = root / "data" / "db"
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))


def get_master_db():
    """Return the SARApp master Mongo database."""
    _ensure_sarapp_db_on_path()
    from sarapp_db.mongo.database_manager import DatabaseManager

    return DatabaseManager().get_master_db()


def get_incident_db(incident_id: str):
    """Return the Mongo database for an incident."""
    _ensure_sarapp_db_on_path()
    from sarapp_db.mongo.database_manager import DatabaseManager

    return DatabaseManager().get_incident_db(str(incident_id))


def strip_mongo_id(document: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return a copy without Mongo's internal ``_id`` field."""
    if document is None:
        return None
    data = dict(document)
    data.pop("_id", None)
    return data
