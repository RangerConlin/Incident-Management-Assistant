"""Checking in a person for the first time should stamp a `master_link` on
the mirrored `incident_personnel` document; later updates must not clobber
an existing link (e.g. one already flagged as a conflict by the sync relay).
"""
from __future__ import annotations

import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

import os

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db
from sarapp_db.mongo.master_link import LINKED
from sarapp_db.mongo.server_identity import get_server_id

INCIDENT_ID = "TEST_CHECKIN_MASTER_LINK"
PERSON_RECORD = 888001


def _reset():
    get_incident_db(INCIDENT_ID)["incident_personnel"].delete_many({})
    get_incident_db(INCIDENT_ID)["resource_status"].delete_many({})
    get_master_db()["personnel"].delete_many({"person_record": PERSON_RECORD})


def test_first_checkin_stamps_master_link():
    _reset()
    try:
        master_doc = get_master_db()["personnel"].insert_one(
            {"_id": "TEST-CHECKIN-MASTER-LINK-PERSON", "person_record": PERSON_RECORD, "name": "Checkin Person"}
        )
        app = create_app()
        with TestClient(app) as client:
            res = client.put(
                f"/api/incidents/{INCIDENT_ID}/checkin/{PERSON_RECORD}",
                json={"status": "Checked In", "arrival_time": "2026-10-06T12:00:00"},
            )
            assert res.status_code == 200, res.text

        doc = get_incident_db(INCIDENT_ID)["incident_personnel"].find_one({"person_record": PERSON_RECORD})
        assert doc is not None
        link = doc["master_link"]
        assert link["sync_state"] == LINKED
        assert link["master_id"] == "TEST-CHECKIN-MASTER-LINK-PERSON"
        assert link["master_collection"] == "personnel"
        assert link["master_server_origin"] == get_server_id()
    finally:
        _reset()


def test_subsequent_checkin_does_not_overwrite_existing_master_link():
    _reset()
    try:
        get_master_db()["personnel"].insert_one(
            {"_id": "TEST-CHECKIN-MASTER-LINK-PERSON-2", "person_record": PERSON_RECORD, "name": "Checkin Person 2"}
        )
        get_incident_db(INCIDENT_ID)["incident_personnel"].insert_one(
            {
                "person_record": PERSON_RECORD,
                "incident_id": INCIDENT_ID,
                "name": "Checkin Person 2",
                "master_link": {
                    "master_collection": "personnel",
                    "master_id": "TEST-CHECKIN-MASTER-LINK-PERSON-2",
                    "master_server_origin": "some-other-server",
                    "central_master_id": None,
                    "last_synced_at": "2020-01-01T00:00:00",
                    "sync_state": "conflict",
                    "conflict": {"fields": ["name"]},
                },
            }
        )

        app = create_app()
        with TestClient(app) as client:
            res = client.put(
                f"/api/incidents/{INCIDENT_ID}/checkin/{PERSON_RECORD}",
                json={"status": "Checked In", "arrival_time": "2026-10-06T12:00:00"},
            )
            assert res.status_code == 200, res.text

        doc = get_incident_db(INCIDENT_ID)["incident_personnel"].find_one({"person_record": PERSON_RECORD})
        link = doc["master_link"]
        # Existing conflict state must survive a routine check-in save.
        assert link["sync_state"] == "conflict"
        assert link["master_server_origin"] == "some-other-server"
    finally:
        _reset()
