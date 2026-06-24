"""Points api_client at the real sarapp_db FastAPI app (in-process, no socket)
for the duration of each ORM test, so modules.safety.orm.service exercises the
actual MongoDB-backed router in data/db/sarapp_db/api/routers/safety.py
instead of needing a real server process running.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import pytest

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from utils.api_client import api_client, DEFAULT_BASE_URL


_TEST_INCIDENT_IDS = ["1001", "2001", "2002"]


def _clear_orm_collections() -> None:
    from sarapp_db.mongo.collection_names import IncidentCollections
    from sarapp_db.mongo.database_manager import get_incident_db

    for incident_id in _TEST_INCIDENT_IDS:
        db = get_incident_db(incident_id)
        db[IncidentCollections.CAP_ORM_FORMS].delete_many({})
        db[IncidentCollections.CAP_ORM_HAZARDS].delete_many({})
        db[IncidentCollections.CAP_ORM_AUDIT].delete_many({})


@pytest.fixture()
def orm_app_client():
    """Activates the in-process test transport and tears it down afterward.

    Also clears this module's test incidents' ORM collections before and
    after each test so runs are deterministic regardless of prior runs.
    """
    from sarapp_db.api.app import create_app

    _clear_orm_collections()
    app = create_app()
    api_client.configure_test_transport(app)
    try:
        yield api_client
    finally:
        api_client.configure(DEFAULT_BASE_URL)
        _clear_orm_collections()
