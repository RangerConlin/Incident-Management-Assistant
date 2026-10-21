from __future__ import annotations

import os
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.collection_names import IncidentCollections, MasterCollections
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db

INCIDENT_ID = "TEST_MOBILE_CONTEXT"
PERSON_RECORD = 9201


def _reset() -> None:
    db = get_incident_db(INCIDENT_ID)
    for collection in (
        IncidentCollections.TEAMS,
        IncidentCollections.INCIDENT_ORG,
        IncidentCollections.INCIDENT_PERSONNEL,
        IncidentCollections.RESOURCE_STATUS,
    ):
        db[collection].delete_many({})
    get_master_db()[MasterCollections.PERSONNEL].delete_many(
        {"person_record": PERSON_RECORD}
    )


def _seed_person() -> None:
    get_master_db()[MasterCollections.PERSONNEL].insert_one(
        {
            "_id": "mobile-context-person",
            "person_record": PERSON_RECORD,
            "person_id": "M-9201",
            "name": "Morgan Lee",
        }
    )


def test_entry_without_team_checks_person_in_and_returns_staff_assignment() -> None:
    _reset()
    _seed_person()
    get_incident_db(INCIDENT_ID)[IncidentCollections.INCIDENT_ORG].insert_one(
        {
            "position_id": 7,
            "title": "Communications Unit Leader",
            "classification": "unit",
            "primary": [{"person_record": PERSON_RECORD, "end_time": None}],
            "deputies": [],
            "staff_assistants": [],
        }
    )

    with TestClient(create_app()) as client:
        response = client.post(
            f"/api/incidents/{INCIDENT_ID}/mobile/entry",
            json={"person_record": PERSON_RECORD},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["team"] is None
    assert payload["resource_status"]["status"] == "Checked In"
    assert payload["staff_assignments"][0]["title"] == "Communications Unit Leader"
    _reset()


def test_entry_with_team_assigns_member_and_returns_team_facts() -> None:
    _reset()
    _seed_person()
    get_incident_db(INCIDENT_ID)[IncidentCollections.TEAMS].insert_one(
        {
            "int_id": 12,
            "name": "Ground Team 2",
            "member_person_records": [],
        }
    )

    with TestClient(create_app()) as client:
        response = client.post(
            f"/api/incidents/{INCIDENT_ID}/mobile/entry",
            json={"person_record": PERSON_RECORD, "team_id": 12},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["team"]["team_id"] == 12
    assert payload["team"]["team_name"] == "Ground Team 2"
    team = get_incident_db(INCIDENT_ID)[IncidentCollections.TEAMS].find_one(
        {"int_id": 12}
    )
    assert team["member_person_records"] == [PERSON_RECORD]
    _reset()
