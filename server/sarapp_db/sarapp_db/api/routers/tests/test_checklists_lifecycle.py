"""Phase 4B: checklist lifecycle (complete/reopen/archive), completion
validation, ICS-214 stream resolution and integration, and reliability
(idempotency/concurrency) tests."""
from __future__ import annotations

import os
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

import sarapp_db.api.routers.checklists as checklists_router
from sarapp_db.api.app import create_app
from sarapp_db.api.routers.auth_sessions import _issue_jwt
from sarapp_db.mongo.collection_names import IncidentCollections, MasterCollections
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db

INCIDENT_A = "TEST_CHECKLISTS_LIFECYCLE_A"
INCIDENT_B = "TEST_CHECKLISTS_LIFECYCLE_B"


def _headers(person_record: int) -> dict[str, str]:
    token = _issue_jwt({"sub": f"user-{person_record}", "person_record": person_record})
    return {"Authorization": f"Bearer {token}"}


def _clear() -> None:
    for incident_id in (INCIDENT_A, INCIDENT_B):
        db = get_incident_db(incident_id)
        db[IncidentCollections.CHECKLISTS].delete_many({})
        db[IncidentCollections.ICS_214_ENTRIES].delete_many({})
        db[IncidentCollections.AUDIT_LOGS].delete_many({})
        db[IncidentCollections.INCIDENT_ORG].delete_many({})
    get_master_db()[MasterCollections.CHECKLISTS].delete_many({})


def _sections(required_pfn: bool = True) -> list[dict]:
    return [
        {
            "id": "sec-1",
            "name": "Equipment",
            "items": [
                {"id": "chk", "item_type": "checkbox", "label": "Checked", "required": True, "na_allowed": False},
                {
                    "id": "pfn",
                    "item_type": "pass_fail_na",
                    "label": "Brake test",
                    "required": required_pfn,
                    "na_allowed": True,
                },
                {"id": "txt", "item_type": "text", "label": "Notes", "required": True, "na_allowed": True},
            ],
        }
    ]


def _create(client: TestClient, incident_id: str = INCIDENT_A, **overrides) -> dict:
    body = {"name": "Safety Inspection", "sections": _sections(), **overrides}
    response = client.post(f"/api/incidents/{incident_id}/checklists", json=body, headers=_headers(101))
    assert response.status_code == 201, response.text
    return response.json()


def _answer_all_required(client: TestClient, incident_id: str, checklist_id: str, actor: int = 101) -> None:
    base = f"/api/incidents/{incident_id}/checklists/{checklist_id}/items"
    for item_id, payload in (("chk", {"value": True}), ("pfn", {"value": "pass"}), ("txt", {"value": "ok"})):
        response = client.post(f"{base}/{item_id}/responses", json=payload, headers=_headers(actor))
        assert response.status_code == 200, response.text


def _ics214_entries_for(incident_id: str, checklist_id: str) -> list[dict]:
    return list(
        get_incident_db(incident_id)[IncidentCollections.ICS_214_ENTRIES].find(
            {"source_record.collection": IncidentCollections.CHECKLISTS, "source_record.record_id": checklist_id}
        )
    )


# ---------------------------------------------------------------------------
# Completion validation / Stage 1
# ---------------------------------------------------------------------------

def test_validate_completion_reports_missing_required() -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc = _create(client)
        response = client.post(
            f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}/validate-completion",
            json={},
            headers=_headers(101),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["can_complete"] is False
        assert set(body["missing_required"]) == {"chk", "pfn", "txt"}
        assert body["ics214_stream_required"] is True
    _clear()


def test_complete_blocked_by_missing_required_responses() -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc = _create(client)
        response = client.post(
            f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}/complete",
            json={"stream": {"incident_wide": True}},
            headers=_headers(101),
        )
        assert response.status_code == 422
        assert "chk" in response.json()["detail"]["missing_required"]
    _clear()


def test_complete_allows_optional_unanswered_item() -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc = _create(client, sections=_sections(required_pfn=False))
        base = f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}"
        client.post(f"{base}/items/chk/responses", json={"value": True}, headers=_headers(101))
        client.post(f"{base}/items/txt/responses", json={"value": "ok"}, headers=_headers(101))
        # "pfn" is optional here and left unanswered.
        response = client.post(f"{base}/complete", json={"stream": {"incident_wide": True}}, headers=_headers(101))
        assert response.status_code == 200, response.text
        assert response.json()["checklist"]["status"] == "completed"
    _clear()


def test_complete_allows_permitted_na_response() -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc = _create(client)
        base = f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}"
        client.post(f"{base}/items/chk/responses", json={"value": True}, headers=_headers(101))
        client.post(f"{base}/items/pfn/responses", json={"na": True}, headers=_headers(101))
        client.post(f"{base}/items/txt/responses", json={"na": True}, headers=_headers(101))
        response = client.post(f"{base}/complete", json={"stream": {"incident_wide": True}}, headers=_headers(101))
        assert response.status_code == 200, response.text
    _clear()


def test_complete_requires_acknowledgment_for_unresolved_failure() -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc = _create(client)
        base = f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}"
        client.post(f"{base}/items/chk/responses", json={"value": True}, headers=_headers(101))
        client.post(f"{base}/items/pfn/responses", json={"value": "fail"}, headers=_headers(101))
        client.post(f"{base}/items/txt/responses", json={"value": "ok"}, headers=_headers(101))

        rejected = client.post(
            f"{base}/complete", json={"stream": {"incident_wide": True}}, headers=_headers(101)
        )
        assert rejected.status_code == 409
        assert rejected.json()["detail"]["unresolved_failures"] == ["pfn"]

        accepted = client.post(
            f"{base}/complete",
            json={"stream": {"incident_wide": True}, "acknowledge_failures": True},
            headers=_headers(101),
        )
        assert accepted.status_code == 200, accepted.text
        checklist = accepted.json()["checklist"]
        assert checklist["status"] == "completed"
        # Preserved, not silently treated as a success.
        failed_item = next(i for i in checklist["sections"][0]["items"] if i["id"] == "pfn")
        assert failed_item["response"]["value"] == "fail"
        history = checklist["lifecycle_history"]
        assert history[-1]["acknowledged_failures"] is True
    _clear()


# ---------------------------------------------------------------------------
# Lifecycle actions: complete / reopen / archive
# ---------------------------------------------------------------------------

def test_normal_completion_records_actor_and_timestamp() -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc = _create(client)
        base = f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}"
        _answer_all_required(client, INCIDENT_A, doc["id"])
        response = client.post(f"{base}/complete", json={"stream": {"incident_wide": True}}, headers=_headers(202))
        assert response.status_code == 200
        checklist = response.json()["checklist"]
        assert checklist["completed_by"] == 202
        assert checklist["completed_at"] is not None
        last = checklist["lifecycle_history"][-1]
        assert last["action"] == "completed"
        assert last["actor_id"] == 202
    _clear()


def test_reopen_requires_reason() -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc = _create(client)
        base = f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}"
        _answer_all_required(client, INCIDENT_A, doc["id"])
        client.post(f"{base}/complete", json={"stream": {"incident_wide": True}}, headers=_headers(101))

        missing_reason = client.post(f"{base}/reopen", json={"reason": "   "}, headers=_headers(101))
        assert missing_reason.status_code == 422

        ok = client.post(f"{base}/reopen", json={"reason": "need to redo brake test"}, headers=_headers(101))
        assert ok.status_code == 200
        assert ok.json()["checklist"]["status"] == "in_progress"
    _clear()


def test_reopen_only_allowed_from_completed() -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc = _create(client)
        response = client.post(
            f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}/reopen",
            json={"reason": "too early"},
            headers=_headers(101),
        )
        assert response.status_code == 409
    _clear()


def test_reopen_preserves_previous_completion_and_response_history() -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc = _create(client)
        base = f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}"
        _answer_all_required(client, INCIDENT_A, doc["id"], actor=101)
        client.post(f"{base}/complete", json={"stream": {"incident_wide": True}}, headers=_headers(101))

        reopened = client.post(f"{base}/reopen", json={"reason": "change of mind"}, headers=_headers(202))
        assert reopened.status_code == 200
        checklist = reopened.json()["checklist"]
        # Previous completion record preserved, not wiped.
        assert checklist["completed_at"] is not None
        assert checklist["completed_by"] == 101

        # Changing a response after reopening keeps the original entry in history.
        changed = client.post(f"{base}/items/chk/responses", json={"value": False}, headers=_headers(202))
        assert changed.status_code == 200
        history = client.get(f"{base}/items/chk/responses").json()["history"]
        assert len(history) == 2
        assert history[0]["recorded_by"] == 101
        assert history[0]["value"] is True
        assert history[1]["recorded_by"] == 202
        assert history[1]["value"] is False
    _clear()


def test_recompletion_after_reopen() -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc = _create(client)
        base = f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}"
        _answer_all_required(client, INCIDENT_A, doc["id"])
        first = client.post(f"{base}/complete", json={"stream": {"incident_wide": True}}, headers=_headers(101))
        assert first.status_code == 200

        client.post(f"{base}/reopen", json={"reason": "redo"}, headers=_headers(101))
        client.post(f"{base}/items/txt/responses", json={"value": "redone"}, headers=_headers(101))

        second = client.post(f"{base}/complete", json={}, headers=_headers(101))
        assert second.status_code == 200
        history = second.json()["checklist"]["lifecycle_history"]
        actions = [entry["action"] for entry in history]
        assert actions.count("completed") == 1
        assert actions.count("recompleted") == 1

        entries = _ics214_entries_for(INCIDENT_A, doc["id"])
        texts = [entry["text"] for entry in entries]
        assert any("completed by" in t and "recompleted" not in t for t in texts)
        assert any("recompleted by" in t for t in texts)
    _clear()


def test_archive_makes_checklist_read_only_and_is_terminal() -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc = _create(client)
        base = f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}"
        archived = client.post(f"{base}/archive", json={}, headers=_headers(101))
        assert archived.status_code == 200
        assert archived.json()["status"] == "archived"
        assert archived.json()["archived_by"] == 101

        blocked_response = client.post(f"{base}/items/chk/responses", json={"value": True}, headers=_headers(101))
        assert blocked_response.status_code == 409

        blocked_complete = client.post(f"{base}/complete", json={}, headers=_headers(101))
        assert blocked_complete.status_code == 409

        blocked_reopen = client.post(f"{base}/reopen", json={"reason": "x"}, headers=_headers(101))
        assert blocked_reopen.status_code == 409

        blocked_archive_again = client.post(f"{base}/archive", json={}, headers=_headers(101))
        assert blocked_archive_again.status_code == 409

        # Archiving never writes an ICS-214 entry.
        assert _ics214_entries_for(INCIDENT_A, doc["id"]) == []
    _clear()


def test_archiving_does_not_touch_source_template() -> None:
    _clear()
    with TestClient(create_app()) as client:
        template = client.post(
            "/api/checklist-templates",
            json={"name": "Template A", "category": "Ops", "sections": _sections(), "active": True},
        ).json()
        created = client.post(
            f"/api/incidents/{INCIDENT_A}/checklists/from-template",
            json={"template_id": template["id"]},
            headers=_headers(101),
        ).json()
        client.post(
            f"/api/incidents/{INCIDENT_A}/checklists/{created['id']}/archive", json={}, headers=_headers(101)
        )
        still_there = client.get(f"/api/checklist-templates/{template['id']}")
        assert still_there.status_code == 200
        assert still_there.json()["active"] is True
    _clear()


# ---------------------------------------------------------------------------
# ICS-214 stream resolution
# ---------------------------------------------------------------------------

def test_completion_requires_explicit_stream_when_none_resolvable() -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc = _create(client)
        _answer_all_required(client, INCIDENT_A, doc["id"])
        response = client.post(
            f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}/complete", json={}, headers=_headers(101)
        )
        assert response.status_code == 422
        assert response.json()["detail"]["ics214_stream_required"] is True
    _clear()


def test_stream_set_at_creation_persists_and_is_reused() -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc = _create(client, stream={"log_keys": ["command"]})
        assert doc["ics214_stream"]["log_keys"] == ["command"]
        _answer_all_required(client, INCIDENT_A, doc["id"])
        # No stream given on this call -- the persisted one from creation is reused.
        response = client.post(
            f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}/complete", json={}, headers=_headers(101)
        )
        assert response.status_code == 200, response.text
        assert response.json()["checklist"]["ics214_stream"]["log_keys"] == ["command"]

        entries = _ics214_entries_for(INCIDENT_A, doc["id"])
        assert len(entries) == 1
        assert entries[0]["log_keys"] == ["command"]
    _clear()


def test_stream_resolution_validates_org_unit_belongs_to_incident() -> None:
    _clear()
    get_incident_db(INCIDENT_A)[IncidentCollections.INCIDENT_ORG].insert_one(
        {"position_id": 5, "title": "Safety Officer"}
    )
    with TestClient(create_app()) as client:
        doc = _create(client)
        _answer_all_required(client, INCIDENT_A, doc["id"])

        unknown_org_unit = client.post(
            f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}/complete",
            json={"stream": {"org_unit_ids": [999]}},
            headers=_headers(101),
        )
        assert unknown_org_unit.status_code == 422

        valid_org_unit = client.post(
            f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}/complete",
            json={"stream": {"org_unit_ids": [5]}},
            headers=_headers(101),
        )
        assert valid_org_unit.status_code == 200, valid_org_unit.text
    _clear()


def test_stream_rejects_unknown_log_key() -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc = _create(client)
        _answer_all_required(client, INCIDENT_A, doc["id"])
        response = client.post(
            f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}/complete",
            json={"stream": {"log_keys": ["not_a_real_key"]}},
            headers=_headers(101),
        )
        assert response.status_code == 422
    _clear()


def test_standalone_checklist_never_requires_or_writes_ics214_stream() -> None:
    _clear()
    with TestClient(create_app()) as client:
        created = client.post(
            "/api/checklists", json={"name": "Personal Checklist", "sections": _sections()}, headers=_headers(101)
        ).json()
        base = f"/api/checklists/{created['id']}"
        for item_id, payload in (("chk", {"value": True}), ("pfn", {"value": "pass"}), ("txt", {"value": "ok"})):
            client.post(f"{base}/items/{item_id}/responses", json=payload, headers=_headers(101))
        completed = client.post(f"{base}/complete", json={}, headers=_headers(101))
        assert completed.status_code == 200, completed.text
        assert completed.json()["ics214_entry_id"] is None
        assert completed.json()["checklist"]["status"] == "completed"

        reopened = client.post(f"{base}/reopen", json={"reason": "redo"}, headers=_headers(101))
        assert reopened.status_code == 200
        assert reopened.json()["ics214_entry_id"] is None

        # Standalone checklists have no /ics214/retry route at all (no incident).
        standalone_paths = {route.path for route in checklists_router.router.routes}
        assert "/checklists/{checklist_id}/ics214/retry" not in standalone_paths
        assert "/incidents/{incident_id}/checklists/{checklist_id}/ics214/retry" in standalone_paths
    _clear()


# ---------------------------------------------------------------------------
# Reliability: idempotency, concurrency, retries
# ---------------------------------------------------------------------------

def test_duplicate_completion_request_is_rejected_not_duplicated() -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc = _create(client)
        base = f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}"
        _answer_all_required(client, INCIDENT_A, doc["id"])

        first = client.post(f"{base}/complete", json={"stream": {"incident_wide": True}}, headers=_headers(101))
        assert first.status_code == 200
        # A retried/duplicate completion request against the now-completed checklist
        # must not succeed a second time or create a second ICS-214 entry.
        second = client.post(f"{base}/complete", json={"stream": {"incident_wide": True}}, headers=_headers(101))
        assert second.status_code == 409

        assert len(_ics214_entries_for(INCIDENT_A, doc["id"])) == 1
    _clear()


def test_claim_transition_is_atomic_under_concurrent_attempts() -> None:
    """Directly exercises `_claim_transition`'s optimistic-concurrency guard:
    two attempts reading the same `lifecycle_event_seq` must not both win."""

    _clear()
    incident_db = get_incident_db(INCIDENT_A)
    repo = checklists_router.ChecklistsRepository(incident_db)
    doc = repo.insert_one(
        {
            "incident_id": INCIDENT_A,
            "int_id": 1,
            "status": "in_progress",
            "lifecycle_event_seq": 0,
            "sections": [],
        }
    )
    checklist_id = str(doc["_id"])

    first = checklists_router._claim_transition(
        repo, checklist_id, 0, ("in_progress",), {"status": "completed"}
    )
    second = checklists_router._claim_transition(
        repo, checklist_id, 0, ("in_progress",), {"status": "completed"}
    )
    assert first is True
    assert second is False
    _clear()


def test_ics214_logging_failure_is_marked_pending_and_recoverable(monkeypatch) -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc = _create(client)
        base = f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}"
        _answer_all_required(client, INCIDENT_A, doc["id"])

        def _boom(*_args, **_kwargs):
            raise RuntimeError("simulated ICS-214 outage")

        monkeypatch.setattr(checklists_router, "_write_ics214_lifecycle_entry", _boom)
        response = client.post(f"{base}/complete", json={"stream": {"incident_wide": True}}, headers=_headers(101))
        assert response.status_code == 200, response.text
        # The lifecycle transition is legitimate even though logging failed.
        assert response.json()["checklist"]["status"] == "completed"
        assert response.json()["ics214_pending"] is True
        assert _ics214_entries_for(INCIDENT_A, doc["id"]) == []

        monkeypatch.undo()
        retried = client.post(f"{base}/ics214/retry", json={}, headers=_headers(101))
        assert retried.status_code == 200
        assert retried.json()["ics214_pending"] is False
        assert len(retried.json()["retried"]) == 1
        assert len(_ics214_entries_for(INCIDENT_A, doc["id"])) == 1
    _clear()


def test_incident_isolation_for_lifecycle_history() -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc_a = _create(client, incident_id=INCIDENT_A)
        cross = client.get(
            f"/api/incidents/{INCIDENT_B}/checklists/{doc_a['id']}/lifecycle-history", headers=_headers(101)
        )
        assert cross.status_code == 404
    _clear()
