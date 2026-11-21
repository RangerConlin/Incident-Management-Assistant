from __future__ import annotations

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db

INCIDENT_ID = "TEST_PROFILE_QR_CHECKIN"
PERSON_ID = "QR-NEW-501"


def _profile() -> dict:
    return {
        "person_id": PERSON_ID,
        "name": "QR Test Person",
        "first_name": "QR Test",
        "last_name": "Person",
        "organization": "County SAR",
        "callsign": "QR-1",
        "emergency_info": {"primary_name": "Test Contact"},
        "contact_info": {"city": "Example"},
        "certifications": [{"cert_type_id": 2003, "level": 1}],
    }


def _clear() -> None:
    master = get_master_db()["personnel"].find_one({"person_id": PERSON_ID})
    get_master_db()["personnel"].delete_many({"person_id": PERSON_ID})
    db = get_incident_db(INCIDENT_ID)
    db["incident_personnel"].delete_many({"person_id": PERSON_ID})
    if master and master.get("person_record") is not None:
        db["resource_status"].delete_many({
            "entity_type": "personnel",
            "record_id": master["person_record"],
        })
    db["teams"].delete_many({"name": "QR Team"})


def test_preview_then_apply_creates_checks_in_and_assigns_person() -> None:
    _clear()
    team = {
        "_id": "qr-test-team",
        "int_id": 12,
        "name": "QR Team",
        "member_person_records": [],
    }
    get_incident_db(INCIDENT_ID)["teams"].insert_one(team)
    try:
        with TestClient(create_app()) as client:
            preview = client.post(
                f"/api/incidents/{INCIDENT_ID}/checkin/resource-qr/preview",
                json={"resource_kind": "personnel", "profile": _profile()},
            )
            assert preview.status_code == 200, preview.text
            assert preview.json()["match_status"] == "new"

            applied = client.post(
                f"/api/incidents/{INCIDENT_ID}/checkin/resource-qr/apply",
                json={
                    "resource_kind": "personnel",
                    "profile": _profile(),
                    "check_in": True,
                    "team_id": 12,
                    "approved_by_person_record": 77,
                },
            )
            assert applied.status_code == 200, applied.text
            result = applied.json()
            assert result["master_action"] == "created"
            assert result["status"] == "Checked In"

        person_record = result["person_record"]
        master = get_master_db()["personnel"].find_one({"person_id": PERSON_ID})
        incident = get_incident_db(INCIDENT_ID)["incident_personnel"].find_one(
            {"person_record": person_record}
        )
        status = get_incident_db(INCIDENT_ID)["resource_status"].find_one(
            {"entity_type": "personnel", "record_id": person_record}
        )
        saved_team = get_incident_db(INCIDENT_ID)["teams"].find_one({"int_id": 12})
        assert master is not None
        assert incident["callsign"] == "QR-1"
        assert status["status"] == "Checked In"
        assert status["status_log"][-1]["changed_by"] == "77"
        assert person_record in saved_team["member_person_records"]
    finally:
        _clear()


def test_apply_rejects_unknown_team_before_creating_person() -> None:
    _clear()
    try:
        with TestClient(create_app()) as client:
            response = client.post(
                f"/api/incidents/{INCIDENT_ID}/checkin/resource-qr/apply",
                json={
                    "resource_kind": "personnel",
                    "profile": _profile(),
                    "check_in": True,
                    "team_id": 999_999,
                },
            )
        assert response.status_code == 404
        assert get_master_db()["personnel"].find_one({"person_id": PERSON_ID}) is None
    finally:
        _clear()
