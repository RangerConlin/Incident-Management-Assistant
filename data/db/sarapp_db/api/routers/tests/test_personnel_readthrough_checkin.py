"""Read-through personnel lookup should support immediate incident check-in.

This mirrors a desktop client connected through cloud_router to a remote
server: the lookup endpoint refreshes local personnel from central first, then
the check-in write uses the refreshed local `person_record` to create incident
rows on that same remote server.
"""
from __future__ import annotations

import os
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.api.routers import personnel as personnel_router
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db

INCIDENT_ID = "TEST_PERSONNEL_READTHROUGH_CHECKIN"
PERSON_ID = "405021"
PERSON_DOC_ID = "TEST-READTHROUGH-PERSON-405021"


def _reset() -> None:
    get_master_db()["personnel"].delete_many({"_id": PERSON_DOC_ID})
    incident_db = get_incident_db(INCIDENT_ID)
    incident_db["resource_status"].delete_many({"resource_id": PERSON_ID})
    incident_db["incident_personnel"].delete_many({"person_id": PERSON_ID})


def test_readthrough_lookup_then_checkin_creates_incident_rows(monkeypatch) -> None:
    _reset()
    calls: list[str] = []

    def fake_refresh(collection: str) -> None:
        calls.append(collection)
        get_master_db()["personnel"].update_one(
            {"_id": PERSON_DOC_ID},
            {
                "$set": {
                    "person_id": PERSON_ID,
                    "name": "Cloud Catalog Person",
                    "phone": "555-0100",
                    "updated_at": "2026-10-10T12:00:00",
                }
            },
            upsert=True,
        )

    monkeypatch.setattr(personnel_router, "refresh_collection_before_read", fake_refresh)

    try:
        app = create_app()
        with TestClient(app) as client:
            lookup = client.get("/api/master/personnel", params={"search": PERSON_ID, "limit": 20})
            assert lookup.status_code == 200, lookup.text
            matches = lookup.json()
            assert len(matches) == 1
            assert matches[0]["person_id"] == PERSON_ID
            person_record = matches[0]["person_record"]
            assert isinstance(person_record, int)

            response = client.put(
                f"/api/incidents/{INCIDENT_ID}/checkin/{person_record}",
                json={"status": "Checked In", "arrival_time": "2026-10-10T13:00:00"},
            )
            assert response.status_code == 200, response.text

        resource_status = get_incident_db(INCIDENT_ID)["resource_status"].find_one(
            {"entity_type": "personnel", "record_id": person_record}
        )
        assert resource_status is not None
        assert resource_status["resource_id"] == PERSON_ID
        assert resource_status["resource_name"] == "Cloud Catalog Person"
        assert resource_status["status"] == "Checked In"

        incident_person = get_incident_db(INCIDENT_ID)["incident_personnel"].find_one(
            {"person_record": person_record}
        )
        assert incident_person is not None
        assert incident_person["person_id"] == PERSON_ID
        assert incident_person["name"] == "Cloud Catalog Person"
        assert calls == ["personnel"]
    finally:
        _reset()
