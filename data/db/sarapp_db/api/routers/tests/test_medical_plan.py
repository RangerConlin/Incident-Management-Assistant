"""ICS-206 merged medical plan storage."""

from __future__ import annotations

import os
import pathlib
import sys

import pytest

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from bridge.medical_bridge import MedicalBridge
from sarapp_db.api.app import create_app
from sarapp_db.mongo.database_manager import get_incident_db
from utils import incident_context
from utils.state import AppState


INCIDENT_ID = "TEST_MEDICAL_PLAN"
OLD_COLLECTIONS = (
    "ics_206_ambulance_services",
    "ics_206_hospitals",
    "ics_206_air_ambulance",
    "ics_206_medical_comms",
    "ics_206_procedures",
    "ics_206_signatures",
)


def _clear(db):
    db["medical_plan"].delete_many({})
    db["ics_206_aid_stations"].delete_many({})
    for name in OLD_COLLECTIONS:
        db[name].delete_many({})


MED_LEAD = {"personnel_id": "7", "name": "Med Lead", "position": "MEDL"}
SAFETY = {"personnel_id": "9", "name": "Safety Officer", "position": "SOFR"}


def _bridge(person=MED_LEAD):
    bridge = MedicalBridge()
    bridge.current_person = lambda: dict(person)  # avoid the personnel API
    bridge.ensure_ics206_tables()
    return bridge


def test_ics206_sections_are_stored_in_medical_plan():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)
    incident_context.set_active_incident(INCIDENT_ID)
    AppState._active_incident_number = INCIDENT_ID
    AppState.set_active_op_period(1)

    bridge = _bridge()
    ambulance_id = bridge.add_record(
        "ambulance_services",
        {
            "name": "County EMS",
            "type": "Ground ALS",
            "service_level": 2,
            "phone": "555-0101",
            "location": "Station 1",
            "notes": "Primary transport",
        },
    )
    bridge.add_record(
        "hospitals",
        {
            "name": "General Hospital",
            "address": "1 Main St",
            "phone": "555-0202",
            "helipad": 1,
            "burn_center": 0,
            "level": "II",
        },
    )
    bridge.save_procedures("Call medical unit before transport.")

    plan_doc = db["medical_plan"].find_one({"incident_id": INCIDENT_ID, "op_period": 1})
    assert plan_doc is not None
    assert plan_doc["plan_id"] == f"{INCIDENT_ID}-MEDICAL-PLAN-1-V1"
    assert plan_doc["ambulance_services"][0]["id"] == ambulance_id
    assert plan_doc["ambulance_services"][0]["name"] == "County EMS"
    assert plan_doc["hospitals"][0]["name"] == "General Hospital"
    assert plan_doc["procedures"]["content"] == "Call medical unit before transport."
    assert plan_doc["version"] == 1
    assert plan_doc["approval_status"] == "not_started"
    assert plan_doc["signatures"]["prepared_by"] == "Med Lead"
    assert plan_doc["signatures"]["position"] == "MEDL"
    assert plan_doc["signatures"]["approved_by"] == ""
    for name in OLD_COLLECTIONS:
        assert db[name].count_documents({}) == 0

    app = create_app()
    with TestClient(app) as client:
        ambulances = client.get(f"/api/incidents/{INCIDENT_ID}/medical/ics206/ambulance-services", params={"op": 1})
        procedures = client.get(f"/api/incidents/{INCIDENT_ID}/medical/ics206/procedures", params={"op": 1})
    assert ambulances.status_code == 200
    assert ambulances.json()[0]["name"] == "County EMS"
    assert procedures.status_code == 200
    assert procedures.json()["content"] == "Call medical unit before transport."

    _clear(db)


def _approve_through_workflow(bridge, monkeypatch, app):
    """Run the real ICS-206 approval chain (MEDL, then SOFR) for the selected version."""
    from modules.approvals.service import ApprovalService
    from utils.api_client import api_client

    api_client.configure_test_transport(app)
    people = {"Medical Unit Leader": (7, MED_LEAD), "Safety Officer": (9, SAFETY)}
    monkeypatch.setattr(
        ApprovalService, "_resolve_actor", lambda self, role: (people[role][0], role)
    )
    incident_id, plan_id = bridge.approval_target()
    service = ApprovalService(incident_id)
    instance = service.start("ics_206", plan_id)
    bridge.mark_pending()
    assert [step.status for step in instance.steps] == ["active", "waiting"]
    for step_id, person_record, who in (("medl_approval", 7, MED_LEAD), ("sofr_approval", 9, SAFETY)):
        instance = service.get("ics_206", plan_id)
        assert service.can_sign(instance, step_id, person_record, "primary")
        assert not service.can_sign(instance, step_id, 123, "primary")
        bridge.current_person = lambda who=who: dict(who)
        instance = service.sign(
            instance,
            step_id=step_id,
            actor_id=str(person_record),
            role_at_time=who["position"],
            assignment_type="primary",
            action="approved",
        )
    assert instance.status == "approved"
    return instance


def test_ics206_versions_approval_workflow_and_lock(monkeypatch):
    db = get_incident_db(INCIDENT_ID)
    _clear(db)
    incident_context.set_active_incident(INCIDENT_ID)
    AppState._active_incident_number = INCIDENT_ID
    AppState.set_active_op_period(1)
    app = create_app()

    bridge = _bridge()
    bridge.add_record("hospitals", {"name": "General Hospital"})
    bridge.add_record("aid_stations", {"name": "Aid 1"})
    assert bridge.current_version() == 1
    assert bridge.approval_status() == "not_started"

    _approve_through_workflow(bridge, monkeypatch, app)
    # The approvals router wrote the outcome to this version's plan doc.
    assert db["medical_plan"].find_one({"version": 1})["approval_status"] == "approved"
    bridge.apply_approval_outcome("approved")
    signatures = bridge.get_signatures()
    assert signatures["prepared_by"] == "Med Lead"
    assert signatures["approved_by"] == "Safety Officer"
    assert signatures["approved_by_position"] == "SOFR"
    assert signatures["approved_at"]
    assert bridge.is_locked()
    with pytest.raises(RuntimeError, match="locked"):
        bridge.add_record("hospitals", {"name": "Nope"})
    with pytest.raises(RuntimeError, match="locked"):
        bridge.save_procedures("nope")

    # A version in review is locked too.
    bridge.current_person = lambda: dict(SAFETY)
    assert bridge.create_new_version("Added hospital") == 2
    assert not bridge.is_locked()
    bridge.mark_pending()
    with pytest.raises(RuntimeError, match="in review"):
        bridge.add_record("hospitals", {"name": "Nope"})
    bridge.apply_approval_outcome("rejected")
    assert bridge.approval_status() == "rejected"
    assert bridge.is_locked()

    # v3 is a draft copy prepared by whoever creates it.
    assert bridge.create_new_version("Fixed after rejection") == 3
    assert not bridge.is_locked()
    assert [row["name"] for row in bridge.list_table("hospitals")] == ["General Hospital"]
    assert [row["name"] for row in bridge.list_table("aid_stations")] == ["Aid 1"]
    signatures = bridge.get_signatures()
    assert signatures["prepared_by"] == "Safety Officer"
    assert signatures["approved_by"] == ""
    bridge.add_record("hospitals", {"name": "Second Hospital"})

    versions = bridge.list_versions()
    assert [(v["version"], v["approval_status"]) for v in versions] == [
        (1, "approved"), (2, "rejected"), (3, "not_started"),
    ]
    assert versions[2]["change_note"] == "Fixed after rejection"

    # v1 is untouched by edits to v3.
    bridge.select_version(1)
    assert [row["name"] for row in bridge.list_table("hospitals")] == ["General Hospital"]

    hospitals_url = f"/api/incidents/{INCIDENT_ID}/medical/ics206/hospitals"
    with TestClient(app) as client:
        # Default serves the latest *approved* version, not the newer drafts.
        default = client.get(hospitals_url, params={"op": 1})
        draft = client.get(hospitals_url, params={"op": 1, "version": 3})
        aid = client.get(f"/api/incidents/{INCIDENT_ID}/medical/ics206/aid-stations", params={"op": 1})
        assert [row["name"] for row in default.json()] == ["General Hospital"]
        assert [row["name"] for row in draft.json()] == ["General Hospital", "Second Hospital"]
        assert aid.status_code == 200, aid.text
        assert [row["name"] for row in aid.json()] == ["Aid 1"]

        # Once v3 is approved it becomes the default.
        bridge.select_version(3)
        _approve_through_workflow(bridge, monkeypatch, app)
        bridge.apply_approval_outcome("approved")
        default = client.get(hospitals_url, params={"op": 1})
        assert [row["name"] for row in default.json()] == ["General Hospital", "Second Hospital"]

    db["approval_instances"].delete_many({})
    db["approval_records"].delete_many({})
    _clear(db)
