"""Stage 6: team readiness validation + conflict prevention, end to end.

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

INCIDENT_ID = "TEST_RESOURCE_VALIDATION"
_PERSON_IDS = [883001, 883002]
_VEHICLE_ID = 883010


def _reset():
    master = get_master_db()
    master[MasterCollections.PERSONNEL].delete_many({"person_record": {"$in": _PERSON_IDS}})
    master[MasterCollections.VEHICLES].delete_many({"vehicle_record": _VEHICLE_ID})
    master[MasterCollections.RESOURCE_TYPES].delete_many({"name": "Stage6 Test Ground Team Type"})
    get_incident_db(INCIDENT_ID)[IncidentCollections.TEAMS].delete_many({})


def _seed_master():
    master = get_master_db()
    master[MasterCollections.PERSONNEL].insert_many(
        [{"person_record": pid, "name": f"Validation Person {pid}", "primary_role": "Ground Team Member"} for pid in _PERSON_IDS]
    )
    master[MasterCollections.VEHICLES].insert_one({"vehicle_record": _VEHICLE_ID, "vehicle_id": "VAL-V1"})


def test_not_evaluated_when_team_has_no_linked_resource_type():
    _reset()
    try:
        _seed_master()
        app = create_app()
        with TestClient(app) as client:
            created = client.post(
                f"/api/incidents/{INCIDENT_ID}/operations/teams",
                json={"name": "GT-1", "team_type": "GT", "member_person_records": [_PERSON_IDS[0]]},
            )
            assert created.status_code == 201
            team_id = created.json()["int_id"]

            validation = client.get(f"/api/incidents/{INCIDENT_ID}/operations/teams/{team_id}/validation")
            assert validation.status_code == 200
            assert validation.json()["outcome"] == "Not Evaluated"
    finally:
        _reset()


def test_qualification_and_min_staffing_outcomes_end_to_end():
    _reset()
    try:
        _seed_master()
        app = create_app()
        with TestClient(app) as client:
            # Resource types are central-catalog authoritative. Seed the
            # local synced copy directly; this test exercises team readiness,
            # not the separately-covered catalog lockdown guard.
            resource_type_id = 883020
            get_master_db()[MasterCollections.RESOURCE_TYPES].insert_one(
                {
                    "resource_type_id": str(resource_type_id),
                    "name": "Stage6 Test Ground Team Type",
                    "category": "Team",
                    "kind": "Ground Search Team",
                    "min_personnel": 2,
                    "required_qualifications": ["Ground Team Member", "Navigator"],
                }
            )

            created = client.post(
                f"/api/incidents/{INCIDENT_ID}/operations/teams",
                json={
                    "name": "GT-1",
                    "team_type": "GT",
                    "resource_type_id": resource_type_id,
                    "member_person_records": [_PERSON_IDS[0]],
                },
            )
            team_id = created.json()["int_id"]

            # Understaffed (1 of 2 minimum) -> Not Ready.
            understaffed = client.get(f"/api/incidents/{INCIDENT_ID}/operations/teams/{team_id}/validation")
            assert understaffed.json()["outcome"] == "Not Ready"

            # Add the second person -- now staffed, but nobody holds
            # "Navigator" -> Ready with Limitations, with the actionable
            # message from the spec.
            client.patch(
                f"/api/incidents/{INCIDENT_ID}/operations/teams/{team_id}",
                json={"member_person_records": [_PERSON_IDS[0], _PERSON_IDS[1]]},
            )
            limited = client.get(f"/api/incidents/{INCIDENT_ID}/operations/teams/{team_id}/validation")
            assert limited.json()["outcome"] == "Ready with Limitations"
            assert any("Navigator" in m for m in limited.json()["messages"])

            # Removing a person from an active team re-evaluates down to
            # Not Ready again -- never a stale/cached outcome.
            client.patch(
                f"/api/incidents/{INCIDENT_ID}/operations/teams/{team_id}",
                json={"member_person_records": [_PERSON_IDS[0]]},
            )
            after_removal = client.get(f"/api/incidents/{INCIDENT_ID}/operations/teams/{team_id}/validation")
            assert after_removal.json()["outcome"] == "Not Ready"
    finally:
        _reset()
        get_master_db()[MasterCollections.RESOURCE_TYPES].delete_many({"name": "Stage6 Test Ground Team Type"})


def test_resource_assignment_conflict_detected_between_two_teams():
    _reset()
    try:
        _seed_master()
        app = create_app()
        with TestClient(app) as client:
            team_a = client.post(
                f"/api/incidents/{INCIDENT_ID}/operations/teams",
                json={"name": "GT-1", "team_type": "GT", "vehicles_json": f"[{_VEHICLE_ID}]"},
            ).json()
            team_b = client.post(
                f"/api/incidents/{INCIDENT_ID}/operations/teams",
                json={"name": "GT-2", "team_type": "GT", "vehicles_json": f"[{_VEHICLE_ID}]"},
            ).json()

            validation_a = client.get(
                f"/api/incidents/{INCIDENT_ID}/operations/teams/{team_a['int_id']}/validation"
            ).json()
            assert validation_a["outcome"] == "Not Ready"
            assert any("GT-2" in m for m in validation_a["messages"])

            validation_b = client.get(
                f"/api/incidents/{INCIDENT_ID}/operations/teams/{team_b['int_id']}/validation"
            ).json()
            assert validation_b["outcome"] == "Not Ready"
            assert any("GT-1" in m for m in validation_b["messages"])
    finally:
        _reset()


def test_disbanded_team_never_conflicts():
    _reset()
    try:
        _seed_master()
        app = create_app()
        with TestClient(app) as client:
            team_a = client.post(
                f"/api/incidents/{INCIDENT_ID}/operations/teams",
                json={"name": "GT-1", "team_type": "GT", "vehicles_json": f"[{_VEHICLE_ID}]"},
            ).json()
            team_b = client.post(
                f"/api/incidents/{INCIDENT_ID}/operations/teams",
                json={"name": "GT-2", "team_type": "GT", "vehicles_json": f"[{_VEHICLE_ID}]"},
            ).json()
            client.post(
                f"/api/incidents/{INCIDENT_ID}/checkin/teams/{team_b['int_id']}/disband",
                json={"disbanded_by": "tester"},
            )

            validation_a = client.get(
                f"/api/incidents/{INCIDENT_ID}/operations/teams/{team_a['int_id']}/validation"
            ).json()
            assert validation_a["outcome"] != "Not Ready" or not any(
                "already committed" in m for m in validation_a["messages"]
            )
    finally:
        _reset()


def test_legacy_team_with_no_resource_type_or_json_fields_loads_without_error():
    """A team document that predates these fields entirely (no
    resource_type_id, no *_json arrays at all) must still validate --
    treated as an empty, unlinked team, never an error."""
    _reset()
    try:
        incident_db = get_incident_db(INCIDENT_ID)
        incident_db[IncidentCollections.TEAMS].insert_one({"int_id": 999, "name": "Legacy Team"})
        app = create_app()
        with TestClient(app) as client:
            response = client.get(f"/api/incidents/{INCIDENT_ID}/operations/teams/999/validation")
            assert response.status_code == 200
            assert response.json()["outcome"] == "Not Evaluated"
    finally:
        _reset()


def test_standing_package_unchanged_after_incident_team_edits():
    """Changing an incident team's composition must never write to the
    standing Resource Package it may have been built from."""
    _reset()
    try:
        _seed_master()
        app = create_app()
        with TestClient(app) as client:
            package = client.post(
                "/api/resource-packages",
                json={
                    "name": "Stage6 Test Standing Package",
                    "resources": [
                        {"resource_type": "personnel", "resource_id": _PERSON_IDS[0], "membership": "fixed"}
                    ],
                },
            ).json()
            before = client.get(f"/api/resource-packages/{package['id']}").json()

            team = client.post(
                f"/api/incidents/{INCIDENT_ID}/operations/teams",
                json={"name": "GT-1", "team_type": "GT", "member_person_records": [_PERSON_IDS[0]]},
            ).json()
            client.patch(
                f"/api/incidents/{INCIDENT_ID}/operations/teams/{team['int_id']}",
                json={"member_person_records": [_PERSON_IDS[0], _PERSON_IDS[1]]},
            )
            client.delete(f"/api/incidents/{INCIDENT_ID}/operations/teams/{team['int_id']}")

            after = client.get(f"/api/resource-packages/{package['id']}").json()
            assert after == before
    finally:
        _reset()
        get_master_db()[MasterCollections.RESOURCE_PACKAGES].delete_many({"name": "Stage6 Test Standing Package"})
