"""Stage 4: Resource Package check-in integration.

Requires a live MongoDB reachable via SARAPP_MONGO_URI (see repo test
conventions).
"""
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

INCIDENT_ID = "TEST_CHECKIN_PACKAGE_ACTIVATION"

_PERSON_IDS = [882001, 882002, 882003]
_VEHICLE_ID = 882010
_SUB_PERSON_ID = 882099


def _reset():
    master = get_master_db()
    master[MasterCollections.PERSONNEL].delete_many({"person_record": {"$in": _PERSON_IDS + [_SUB_PERSON_ID]}})
    master[MasterCollections.VEHICLES].delete_many({"vehicle_record": _VEHICLE_ID})
    master[MasterCollections.RESOURCE_PACKAGES].delete_many({"name": {"$regex": "^Stage4 Test"}})
    incident_db = get_incident_db(INCIDENT_ID)
    incident_db[IncidentCollections.RESOURCE_STATUS].delete_many({})
    incident_db[IncidentCollections.PACKAGE_ACTIVATIONS].delete_many({})


def _seed_master():
    master = get_master_db()
    master[MasterCollections.PERSONNEL].insert_many(
        [{"person_record": pid, "name": f"Package Person {pid}"} for pid in _PERSON_IDS + [_SUB_PERSON_ID]]
    )
    master[MasterCollections.VEHICLES].insert_one({"vehicle_record": _VEHICLE_ID, "vehicle_id": "PKG4-V1"})


def _create_package(client) -> dict:
    payload = {
        "name": "Stage4 Test Ground Team",
        "default_team_designation": "GT-9",
        "resources": [
            {"resource_type": "personnel", "resource_id": _PERSON_IDS[0], "membership": "fixed", "role": "Team Leader"},
            {"resource_type": "personnel", "resource_id": _PERSON_IDS[1], "membership": "fixed", "role": "Member"},
            {"resource_type": "personnel", "resource_id": _PERSON_IDS[2], "membership": "preferred", "role": "Member"},
            {"resource_type": "vehicle", "resource_id": _VEHICLE_ID, "membership": "fixed", "role": "Primary"},
        ],
    }
    response = client.post("/api/resource-packages", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_package_suggestions_show_mixed_checked_in_state():
    _reset()
    try:
        _seed_master()
        app = create_app()
        with TestClient(app) as client:
            pkg = _create_package(client)

            # Person 0 checks in first.
            checkin_resp = client.put(
                f"/api/incidents/{INCIDENT_ID}/checkin/{_PERSON_IDS[0]}",
                json={"status": "Checked In"},
            )
            assert checkin_resp.status_code == 200

            suggestions = client.get(
                f"/api/incidents/{INCIDENT_ID}/checkin/package-suggestions/personnel/{_PERSON_IDS[0]}"
            )
            assert suggestions.status_code == 200
            rows = suggestions.json()
            assert len(rows) == 1
            members = {m["resource_id"]: m for m in rows[0]["members"]}
            assert members[_PERSON_IDS[0]]["checked_in"] is True
            assert members[_PERSON_IDS[1]]["checked_in"] is False
            assert members[_VEHICLE_ID]["checked_in"] is False
            assert rows[0]["checked_in_count"] == 1
            assert rows[0]["total_count"] == 4
    finally:
        _reset()


def test_activate_package_checks_in_only_confirmed_with_substitution_and_omission():
    _reset()
    try:
        _seed_master()
        app = create_app()
        with TestClient(app) as client:
            pkg = _create_package(client)

            body = {
                "activated_by": "ic-test",
                "confirmed": [
                    {"resource_type": "personnel", "resource_id": _PERSON_IDS[0]},
                    {"resource_type": "vehicle", "resource_id": _VEHICLE_ID},
                ],
                "substitutions": [
                    {
                        "original": {"resource_type": "personnel", "resource_id": _PERSON_IDS[1]},
                        "substitute": {"resource_type": "personnel", "resource_id": _SUB_PERSON_ID},
                    }
                ],
                "omitted": [
                    {"resource_type": "personnel", "resource_id": _PERSON_IDS[2]},
                ],
            }
            response = client.post(f"/api/incidents/{INCIDENT_ID}/checkin/packages/{pkg['id']}/activate", json=body)
            assert response.status_code == 201, response.text
            activation = response.json()
            assert activation["package_id"] == pkg["id"]
            assert len(activation["substitutions"]) == 1
            assert len(activation["omitted_members"]) == 1

            # Confirmed + substitute are checked in.
            p0 = client.get(f"/api/incidents/{INCIDENT_ID}/checkin/{_PERSON_IDS[0]}")
            assert p0.status_code == 200 and p0.json()["checked_in"] is True

            sub = client.get(f"/api/incidents/{INCIDENT_ID}/checkin/{_SUB_PERSON_ID}")
            assert sub.status_code == 200 and sub.json()["checked_in"] is True

            # Original member who was substituted away is never auto-checked-in.
            original_still_absent = client.get(f"/api/incidents/{INCIDENT_ID}/checkin/{_PERSON_IDS[1]}")
            assert original_still_absent.status_code == 404

            # Omitted member is never auto-checked-in.
            omitted_absent = client.get(f"/api/incidents/{INCIDENT_ID}/checkin/{_PERSON_IDS[2]}")
            assert omitted_absent.status_code == 404

            vehicle_status = client.get(
                f"/api/incidents/{INCIDENT_ID}/resources/vehicle/{_VEHICLE_ID}"
            )
            assert vehicle_status.status_code == 200
            assert vehicle_status.json()["status"] in ("Checked In",)

            activations = client.get(f"/api/incidents/{INCIDENT_ID}/checkin/packages/activations")
            assert activations.status_code == 200
            assert len(activations.json()) == 1
    finally:
        _reset()


def test_activate_package_does_not_duplicate_already_checked_in_resource():
    """Repeated check-in/activation must never duplicate a resource record,
    and must never downgrade someone already committed to a team back to
    'Checked In'."""
    _reset()
    try:
        _seed_master()
        app = create_app()
        with TestClient(app) as client:
            pkg = _create_package(client)

            # Pre-assign person 0 to a team (status Assigned) before activation.
            client.put(
                f"/api/incidents/{INCIDENT_ID}/checkin/{_PERSON_IDS[0]}",
                json={"status": "Assigned", "team_id": "7"},
            )

            body = {
                "activated_by": "ic-test",
                "confirmed": [{"resource_type": "personnel", "resource_id": _PERSON_IDS[0]}],
                "substitutions": [],
                "omitted": [],
            }
            response = client.post(f"/api/incidents/{INCIDENT_ID}/checkin/packages/{pkg['id']}/activate", json=body)
            assert response.status_code == 201

            still_assigned = client.get(f"/api/incidents/{INCIDENT_ID}/checkin/{_PERSON_IDS[0]}")
            assert still_assigned.status_code == 200
            assert still_assigned.json()["status"] == "Assigned"

            incident_db = get_incident_db(INCIDENT_ID)
            matching = list(
                incident_db[IncidentCollections.RESOURCE_STATUS].find(
                    {"entity_type": "personnel", "record_id": _PERSON_IDS[0]}
                )
            )
            assert len(matching) == 1  # never duplicated
    finally:
        _reset()


def test_package_status_endpoint_independent_of_trigger_resource():
    _reset()
    try:
        _seed_master()
        app = create_app()
        with TestClient(app) as client:
            pkg = _create_package(client)
            status = client.get(f"/api/incidents/{INCIDENT_ID}/checkin/packages/{pkg['id']}/status")
            assert status.status_code == 200
            payload = status.json()
            assert payload["package_name"] == "Stage4 Test Ground Team"
            assert payload["total_count"] == 4
            assert payload["checked_in_count"] == 0
    finally:
        _reset()
