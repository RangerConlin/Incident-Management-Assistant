"""Points api_client at the real sarapp_db FastAPI app (in-process, no socket)
so modules.personnel.units_organizations exercises the actual MongoDB-backed
router in data/db/sarapp_db/api/routers/organizations.py instead of needing a
real server process running (and silently swallowing the resulting errors —
the repository methods here catch all exceptions and return [] on failure).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from utils.api_client import api_client, DEFAULT_BASE_URL


def _clear_master_collections() -> None:
    from sarapp_db.mongo.collection_names import MasterCollections
    from sarapp_db.mongo.database_manager import get_master_db

    db = get_master_db()
    db[MasterCollections.RANK_STRUCTURES].delete_many({})
    db[MasterCollections.RANKS].delete_many({})
    db[MasterCollections.RANK_STRUCTURE_AUDIT_LOG].delete_many({})
    db[MasterCollections.ORGANIZATION_TYPES].delete_many({})


@pytest.fixture()
def org_app_client():
    from sarapp_db.api.app import create_app

    _clear_master_collections()
    app = create_app()
    api_client.configure_test_transport(app)
    try:
        yield api_client
    finally:
        api_client.configure(DEFAULT_BASE_URL)
        _clear_master_collections()
