"""Focused tests for the shared cross-module approval engine."""

from __future__ import annotations

import os
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

import sarapp_db.api.routers.approvals as approvals_router
from sarapp_db.api.app import create_app
from sarapp_db.api.routers.auth_sessions import _issue_jwt, _sessions_col, resolve_request_person
from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db

INCIDENT_ID = "TEST_GENERIC_APPROVALS"


def _reset():
    db = get_incident_db(INCIDENT_ID)
    for name in (
        IncidentCollections.APPROVAL_INSTANCES,
        IncidentCollections.APPROVAL_RECORDS,
        IncidentCollections.COMMUNICATIONS_PLAN,
        IncidentCollections.IWI_REPORTS,
        IncidentCollections.IAP_PACKAGES,
        IncidentCollections.WORK_ASSIGNMENTS,
        IncidentCollections.NOTIFICATIONS,
    ):
        db[name].delete_many({})
    return db


def _headers(person_record: int) -> dict[str, str]:
    token = _issue_jwt({"sub": f"user-{person_record}", "person_record": person_record})
    return {"Authorization": f"Bearer {token}"}


def test_desktop_session_identity_is_verified():
    sessions = _sessions_col()
    sessions.delete_many({"session_id": "approval-test-session"})
    sessions.insert_one({
        "session_id": "approval-test-session",
        "person_record": 707,
        "ended_at": None,
    })
    try:
        assert resolve_request_person(
            authorization=None,
            session_id="approval-test-session",
            claimed_person_record=707,
        ) == 707
        try:
            resolve_request_person(
                authorization=None,
                session_id="approval-test-session",
                claimed_person_record=708,
            )
        except Exception as exc:
            assert getattr(exc, "status_code", None) == 403
        else:
            raise AssertionError("mismatched desktop actor was accepted")
    finally:
        sessions.delete_many({"session_id": "approval-test-session"})


def test_sequential_chain_duplicate_start_and_verified_signer(monkeypatch):
    db = _reset()
    db[IncidentCollections.COMMUNICATIONS_PLAN].insert_one(
        {"incident_id": INCIDENT_ID, "plan_id": "plan-1", "approval_status": "not_started"}
    )
    monkeypatch.setattr(
        approvals_router, "_resolve_actor", lambda _incident, _role: (101, "Communications Unit Leader")
    )
    base = f"/api/incidents/{INCIDENT_ID}/approvals/ics_205/plan-1"
    with TestClient(create_app()) as client:
        started = client.post(f"{base}/start", json={})
        assert started.status_code == 200
        assert started.json()["steps"][0]["status"] == "active"
        assert client.post(f"{base}/start", json={}).status_code == 409

        wrong = client.post(
            f"{base}/sign",
            headers=_headers(202),
            json={"step_id": "coml_signoff", "actor_id": 101, "action": "approved"},
        )
        assert wrong.status_code == 403

        signed = client.post(
            f"{base}/sign",
            headers=_headers(101),
            json={"step_id": "coml_signoff", "actor_id": 101, "action": "approved"},
        )
        assert signed.status_code == 200
        assert signed.json()["status"] == "approved"
    assert db[IncidentCollections.COMMUNICATIONS_PLAN].find_one({"plan_id": "plan-1"})["approval_status"] == "approved"


def test_parallel_chain_waits_for_both_and_rejection_is_terminal(monkeypatch):
    db = _reset()
    db[IncidentCollections.IWI_REPORTS].insert_one(
        {"incident_id": INCIDENT_ID, "id": "iwi-1", "approval_status": "not_started"}
    )
    people = {"Safety Officer": 301, "Incident Commander": 302}
    monkeypatch.setattr(
        approvals_router, "_resolve_actor", lambda _incident, role: (people[role], role)
    )
    base = f"/api/incidents/{INCIDENT_ID}/approvals/iwi_report/iwi-1"
    with TestClient(create_app()) as client:
        assert client.post(f"{base}/start", json={}).status_code == 200
        first = client.post(
            f"{base}/sign", headers=_headers(301),
            json={"step_id": "sofr_signoff", "actor_id": 301, "action": "approved"},
        )
        assert first.json()["status"] == "pending"
        rejected = client.post(
            f"{base}/sign", headers=_headers(302),
            json={"step_id": "ic_signoff", "actor_id": 302, "action": "rejected"},
        )
        assert rejected.json()["status"] == "rejected"
    assert db[IncidentCollections.IWI_REPORTS].find_one({"id": "iwi-1"})["approval_status"] == "rejected"


def test_iap_requires_approved_forms_and_writes_package_status(monkeypatch):
    db = _reset()
    db[IncidentCollections.IAP_PACKAGES].insert_one({
        "incident_id": INCIDENT_ID,
        "op_number": 4,
        "status": "draft",
        "forms": [{"form_id": "ICS-202", "status": "draft"}],
    })
    monkeypatch.setattr(
        approvals_router, "_resolve_actor", lambda _incident, _role: (401, "Incident Commander")
    )
    base = f"/api/incidents/{INCIDENT_ID}/approvals/iap/4"
    with TestClient(create_app()) as client:
        assert client.post(f"{base}/start", json={}).status_code == 400
        db[IncidentCollections.IAP_PACKAGES].update_one(
            {"op_number": 4}, {"$set": {"forms.0.status": "approved"}}
        )
        assert client.post(f"{base}/start", json={}).status_code == 200
        response = client.post(
            f"{base}/sign", headers=_headers(401),
            json={"step_id": "ic_approval", "actor_id": 401, "action": "approved"},
        )
        assert response.status_code == 200
    assert db[IncidentCollections.IAP_PACKAGES].find_one({"op_number": 4})["status"] == "approved"


def test_work_assignment_four_role_parallel_chain_and_notify_endpoint(monkeypatch):
    """Safety Officer, OSC, PSC, and LSC all activate together; only Safety's
    sign-off is a real approve/reject gate, the rest just acknowledge."""
    db = _reset()
    db[IncidentCollections.WORK_ASSIGNMENTS].insert_one(
        {
            "incident_id": INCIDENT_ID,
            "int_id": 14,
            "approval_status": "not_started",
            "safety_status": "Unchecked",
            "planning_status": "Under Review",
        }
    )
    people = {
        "Safety Officer": 501,
        "Operations Section Chief": 502,
        "Planning Section Chief": 503,
        "Logistics Section Chief": 504,
    }
    monkeypatch.setattr(
        approvals_router, "_resolve_actor", lambda _incident, role: (people[role], role)
    )
    base = f"/api/incidents/{INCIDENT_ID}/approvals/work_assignment/14"
    with TestClient(create_app()) as client:
        started = client.post(f"{base}/start", json={})
        assert started.status_code == 200
        steps = {s["step_id"]: s for s in started.json()["steps"]}
        assert all(s["status"] == "active" for s in steps.values())

        # Manual "Send for Review" nudge re-notifies an already-active step.
        notified = client.post(f"{base}/steps/osc_review/notify")
        assert notified.status_code == 200

        # A step with nobody resolved (or not active) can't be nudged.
        bogus = client.post(f"{base}/steps/no_such_step/notify")
        assert bogus.status_code == 404

        for step_id, actor in (
            ("osc_review", 502),
            ("psc_review", 503),
            ("lsc_review", 504),
        ):
            ack = client.post(
                f"{base}/sign", headers=_headers(actor),
                json={"step_id": step_id, "actor_id": actor, "action": "acknowledged"},
            )
            assert ack.status_code == 200
            assert ack.json()["status"] == "pending"

        final = client.post(
            f"{base}/sign", headers=_headers(501),
            json={"step_id": "sofr_approval", "actor_id": 501, "action": "approved"},
        )
        assert final.status_code == 200
        assert final.json()["status"] == "approved"
    assert db[IncidentCollections.WORK_ASSIGNMENTS].find_one({"int_id": 14})["approval_status"] == "approved"


def test_work_assignment_rejection_sets_safety_concern_and_can_be_resubmitted(monkeypatch):
    db = _reset()
    db[IncidentCollections.WORK_ASSIGNMENTS].insert_one(
        {
            "incident_id": INCIDENT_ID,
            "int_id": 21,
            "approval_status": "not_started",
            "safety_status": "Unchecked",
            "planning_status": "Under Review",
        }
    )
    people = {
        "Safety Officer": 601,
        "Operations Section Chief": 602,
        "Planning Section Chief": 603,
        "Logistics Section Chief": 604,
    }
    monkeypatch.setattr(
        approvals_router, "_resolve_actor", lambda _incident, role: (people[role], role)
    )
    base = f"/api/incidents/{INCIDENT_ID}/approvals/work_assignment/21"
    with TestClient(create_app()) as client:
        assert client.post(f"{base}/start", json={}).status_code == 200

        rejected = client.post(
            f"{base}/sign", headers=_headers(601),
            json={
                "step_id": "sofr_approval", "actor_id": 601, "action": "rejected",
                "notes": "Drainage route hasn't been re-assessed for the heat advisory.",
            },
        )
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "rejected"

        doc = db[IncidentCollections.WORK_ASSIGNMENTS].find_one({"int_id": 21})
        assert doc["approval_status"] == "rejected"
        assert doc["safety_status"] == "Safety Concern"
        # Planning status is left alone by a safety rejection.
        assert doc["planning_status"] == "Under Review"

        # A second start() while the old instance is still "pending" would
        # 409; a rejected one does not block resubmission.
        restarted = client.post(f"{base}/start", json={})
        assert restarted.status_code == 200
        steps = {s["step_id"]: s for s in restarted.json()["steps"]}
        assert all(s["status"] == "active" for s in steps.values())

        doc = db[IncidentCollections.WORK_ASSIGNMENTS].find_one({"int_id": 21})
        assert doc["approval_status"] == "pending"

        # The rejection reason is preserved in the audit trail even after
        # the instance itself was replaced by the resubmission.
        records = list(db[IncidentCollections.APPROVAL_RECORDS].find(
            {"incident_id": INCIDENT_ID, "entity_type": "work_assignment", "entity_id": "21"}
        ))
        assert any(r["action"] == "rejected" and "heat advisory" in (r.get("notes") or "") for r in records)
