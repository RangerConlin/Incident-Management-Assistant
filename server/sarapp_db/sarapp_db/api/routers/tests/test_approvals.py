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
