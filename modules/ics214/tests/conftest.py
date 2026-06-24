"""Points api_client at the real sarapp_db FastAPI app (in-process, no socket)
for ICS-214 tests, so modules.ics214.services exercises the actual
MongoDB-backed router in data/db/sarapp_db/api/routers/ics214.py instead of
needing a real server process running.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from utils.api_client import api_client, DEFAULT_BASE_URL

_TEST_INCIDENT_IDS = ["ics214-test", "ics214-test2", "incident", "m1"]


def _clear_ics214_collections() -> None:
    from sarapp_db.mongo.collection_names import IncidentCollections
    from sarapp_db.mongo.database_manager import get_incident_db

    for incident_id in _TEST_INCIDENT_IDS:
        db = get_incident_db(incident_id)
        db[IncidentCollections.ICS_214_LOGS].delete_many({})


@pytest.fixture()
def ics214_app_client():
    from sarapp_db.api.app import create_app

    _clear_ics214_collections()
    app = create_app()
    api_client.configure_test_transport(app)
    try:
        yield api_client
    finally:
        api_client.configure(DEFAULT_BASE_URL)
        _clear_ics214_collections()
