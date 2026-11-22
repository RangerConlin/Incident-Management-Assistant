"""Router tests for checklist instances: templates, blank, responses,
item types, N/A, validation, attribution/history, concurrency, incident
isolation, progress/failures, lifecycle, and standalone checklists."""
from __future__ import annotations

import os
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.api.routers.auth_sessions import _issue_jwt
from sarapp_db.mongo.collection_names import IncidentCollections, MasterCollections
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db

INCIDENT_A = "TEST_CHECKLISTS_A"
INCIDENT_B = "TEST_CHECKLISTS_B"


def _headers(person_record: int) -> dict[str, str]:
    token = _issue_jwt({"sub": f"user-{person_record}", "person_record": person_record})
    return {"Authorization": f"Bearer {token}"}


def _clear() -> None:
    get_incident_db(INCIDENT_A)[IncidentCollections.CHECKLISTS].delete_many({})
    get_incident_db(INCIDENT_B)[IncidentCollections.CHECKLISTS].delete_many({})
    get_master_db()[MasterCollections.CHECKLIST_TEMPLATES].delete_many({})
    get_master_db()[MasterCollections.CHECKLISTS].delete_many({})


def _full_sections() -> list[dict]:
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
                    "required": True,
                    "na_allowed": True,
                },
                {"id": "txt", "item_type": "text", "label": "Notes", "required": True, "na_allowed": True},
                {
                    "id": "num",
                    "item_type": "numeric",
                    "label": "Fuel level",
                    "unit": "%",
                    "min_value": 0,
                    "max_value": 100,
                    "required": False,
                    "na_allowed": False,
                },
                {
                    "id": "sel",
                    "item_type": "selection",
                    "label": "Condition",
                    "options": [{"id": "good", "label": "Good"}, {"id": "bad", "label": "Bad"}],
                    "required": False,
                    "na_allowed": True,
                },
            ],
        }
    ]


def _create_blank(client: TestClient, incident_id: str = INCIDENT_A, **overrides) -> dict:
    body = {"name": "Inspection", "sections": _full_sections(), **overrides}
    response = client.post(
        f"/api/incidents/{incident_id}/checklists", json=body, headers=_headers(101)
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_blank_checklist() -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc = _create_blank(client)
        assert doc["status"] == "not_started"
        assert doc["incident_id"] == INCIDENT_A
        assert doc["created_by"] == 101
        assert len(doc["sections"][0]["items"]) == 5
        for item in doc["sections"][0]["items"]:
            assert item["response"] is None
            assert item["history"] == []
    _clear()


def test_template_snapshot_is_independent_of_later_template_edits() -> None:
    _clear()
    with TestClient(create_app()) as client:
        template = client.post(
            "/api/checklist-templates",
            json={
                "name": "Radio Check",
                "category": "Comms",
                "sections": _full_sections(),
                "active": True,
            },
        ).json()

        instance = client.post(
            f"/api/incidents/{INCIDENT_A}/checklists/from-template",
            json={"template_id": template["id"]},
            headers=_headers(101),
        )
        assert instance.status_code == 201
        instance_body = instance.json()
        assert instance_body["template_id"] == template["id"]
        assert instance_body["name"] == "Radio Check"

        # Edit the template after the instance was created.
        edited = dict(template)
        edited["name"] = "Radio Check (Revised)"
        edited["sections"][0]["items"][0]["label"] = "Renamed label"
        put = client.put(f"/api/checklist-templates/{template['id']}", json=edited)
        assert put.status_code == 200

        # Delete (deactivate) the template entirely.
        client.patch(f"/api/checklist-templates/{template['id']}/active", json={"active": False})

        refetched = client.get(
            f"/api/incidents/{INCIDENT_A}/checklists/{instance_body['id']}"
        ).json()
        assert refetched["name"] == "Radio Check"
        assert refetched["sections"][0]["items"][0]["label"] == "Checked"
    _clear()


def test_all_five_item_types_record_valid_responses() -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc = _create_blank(client)
        checklist_id = doc["id"]
        base = f"/api/incidents/{INCIDENT_A}/checklists/{checklist_id}/items"

        cases = [
            ("chk", {"value": True}),
            ("pfn", {"value": "pass"}),
            ("txt", {"value": "All good"}),
            ("num", {"value": 87.5}),
            ("sel", {"value": "good"}),
        ]
        for item_id, payload in cases:
            response = client.post(f"{base}/{item_id}/responses", json=payload, headers=_headers(101))
            assert response.status_code == 200, response.text
            assert response.json()["response"]["recorded_by"] == 101

        checklist = client.get(f"/api/incidents/{INCIDENT_A}/checklists/{checklist_id}").json()
        assert checklist["status"] == "in_progress"
        for item in checklist["sections"][0]["items"]:
            assert item["response"] is not None
    _clear()


def test_na_requires_na_allowed() -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc = _create_blank(client)
        base = f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}/items"

        # "chk" has na_allowed=False.
        rejected = client.post(f"{base}/chk/responses", json={"na": True}, headers=_headers(101))
        assert rejected.status_code == 422

        # "pfn" has na_allowed=True.
        allowed = client.post(f"{base}/pfn/responses", json={"na": True}, headers=_headers(101))
        assert allowed.status_code == 200
        assert allowed.json()["response"]["na"] is True
        assert allowed.json()["response"]["value"] is None
    _clear()


def test_required_text_item_rejects_blank_response() -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc = _create_blank(client)
        base = f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}/items"
        response = client.post(f"{base}/txt/responses", json={"value": "   "}, headers=_headers(101))
        assert response.status_code == 422
    _clear()


def test_numeric_bounds_are_enforced() -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc = _create_blank(client)
        base = f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}/items"
        too_high = client.post(f"{base}/num/responses", json={"value": 150}, headers=_headers(101))
        assert too_high.status_code == 422
        too_low = client.post(f"{base}/num/responses", json={"value": -5}, headers=_headers(101))
        assert too_low.status_code == 422
        ok = client.post(f"{base}/num/responses", json={"value": 42.25}, headers=_headers(101))
        assert ok.status_code == 200
        assert ok.json()["response"]["value"] == 42.25
    _clear()


def test_selection_rejects_unknown_option() -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc = _create_blank(client)
        base = f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}/items"
        response = client.post(f"{base}/sel/responses", json={"value": "unknown"}, headers=_headers(101))
        assert response.status_code == 422
    _clear()


def test_pass_fail_na_distinguishes_fail_from_unanswered() -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc = _create_blank(client)
        base = f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}/items"
        client.post(f"{base}/pfn/responses", json={"value": "fail"}, headers=_headers(101))

        progress = client.get(
            f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}/progress"
        ).json()
        assert progress["failed_items"] == ["pfn"]
        assert progress["answered_items"] == 1
        assert any(f["item_id"] == "pfn" for f in progress["unresolved_failures"])
    _clear()


def test_actor_mismatch_is_rejected() -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc = _create_blank(client)
        base = f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}/items"
        response = client.post(
            f"{base}/chk/responses",
            json={"value": True, "actor_id": 999},
            headers=_headers(101),
        )
        assert response.status_code == 403
    _clear()


def test_response_change_preserves_history_and_original_author() -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc = _create_blank(client)
        base = f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}/items"

        first = client.post(f"{base}/chk/responses", json={"value": False}, headers=_headers(101))
        assert first.status_code == 200
        second = client.post(f"{base}/chk/responses", json={"value": True}, headers=_headers(202))
        assert second.status_code == 200

        history = client.get(f"{base}/chk/responses").json()["history"]
        assert len(history) == 2
        assert history[0]["recorded_by"] == 101
        assert history[0]["value"] is False
        assert history[1]["recorded_by"] == 202
        assert history[1]["value"] is True

        current = client.get(f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}").json()
        current_item = next(i for i in current["sections"][0]["items"] if i["id"] == "chk")
        assert current_item["response"]["recorded_by"] == 202
        assert current_item["response"]["value"] is True
    _clear()


def test_concurrent_responses_to_different_items_do_not_clobber_each_other() -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc = _create_blank(client)
        base = f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}/items"

        # Simulates two users responding to two different items "at the
        # same time" -- regardless of interleaving, both updates must
        # persist; this exercises the atomic per-item array-filter write
        # rather than a whole-document read-modify-write.
        r1 = client.post(f"{base}/chk/responses", json={"value": True}, headers=_headers(101))
        r2 = client.post(f"{base}/num/responses", json={"value": 55}, headers=_headers(202))
        assert r1.status_code == 200
        assert r2.status_code == 200

        checklist = client.get(f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}").json()
        items_by_id = {i["id"]: i for i in checklist["sections"][0]["items"]}
        assert items_by_id["chk"]["response"]["value"] is True
        assert items_by_id["num"]["response"]["value"] == 55
        assert items_by_id["pfn"]["response"] is None
    _clear()


def test_incident_isolation() -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc_a = _create_blank(client, incident_id=INCIDENT_A)
        doc_b = _create_blank(client, incident_id=INCIDENT_B)

        list_a = client.get(f"/api/incidents/{INCIDENT_A}/checklists").json()
        assert [row["id"] for row in list_a] == [doc_a["id"]]

        cross_incident = client.get(f"/api/incidents/{INCIDENT_B}/checklists/{doc_a['id']}")
        assert cross_incident.status_code == 404

        same_incident = client.get(f"/api/incidents/{INCIDENT_B}/checklists/{doc_b['id']}")
        assert same_incident.status_code == 200
    _clear()


def test_progress_calculation() -> None:
    _clear()
    with TestClient(create_app()) as client:
        doc = _create_blank(client)
        base = f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}/items"

        client.post(f"{base}/chk/responses", json={"value": True}, headers=_headers(101))
        client.post(f"{base}/pfn/responses", json={"na": True}, headers=_headers(101))

        progress = client.get(
            f"/api/incidents/{INCIDENT_A}/checklists/{doc['id']}/progress"
        ).json()
        assert progress["total_items"] == 5
        assert progress["answered_items"] == 2
        assert progress["na_items"] == 1
        assert progress["failed_items"] == []
        # "txt" is required and unanswered.
        assert "txt" in progress["unanswered_required_items"]
        assert progress["completion_percentage"] == 40.0
    _clear()


def test_status_lifecycle_transitions() -> None:
    """Basic end-to-end sanity for the Phase 4B explicit lifecycle actions
    (complete/reopen/archive) replacing Phase 4A's generic status PATCH.
    See test_checklists_lifecycle.py for the full Phase 4B coverage."""

    _clear()
    with TestClient(create_app()) as client:
        doc = _create_blank(client)
        checklist_id = doc["id"]
        base = f"/api/incidents/{INCIDENT_A}/checklists/{checklist_id}"

        assert doc["status"] == "not_started"
        for item_id, payload in (("chk", {"value": True}), ("pfn", {"value": "pass"}), ("txt", {"value": "ok"})):
            client.post(f"{base}/items/{item_id}/responses", json=payload, headers=_headers(101))

        completed = client.post(
            f"{base}/complete", json={"stream": {"incident_wide": True}}, headers=_headers(101)
        )
        assert completed.status_code == 200, completed.text
        assert completed.json()["checklist"]["status"] == "completed"
        assert completed.json()["checklist"]["completed_at"] is not None

        reopened = client.post(f"{base}/reopen", json={"reason": "found a mistake"}, headers=_headers(101))
        assert reopened.status_code == 200, reopened.text
        assert reopened.json()["checklist"]["status"] == "in_progress"
        # Preserves the previous completion record rather than clearing it.
        assert reopened.json()["checklist"]["completed_at"] is not None

        recompleted = client.post(f"{base}/complete", json={}, headers=_headers(101))
        assert recompleted.status_code == 200, recompleted.text

        archived = client.post(f"{base}/archive", json={}, headers=_headers(101))
        assert archived.status_code == 200
        assert archived.json()["archived_at"] is not None

        blocked_reopen = client.post(f"{base}/reopen", json={"reason": "too late"}, headers=_headers(101))
        assert blocked_reopen.status_code == 409

        response_after_archive = client.post(
            f"{base}/items/chk/responses", json={"value": False}, headers=_headers(101)
        )
        assert response_after_archive.status_code == 409
    _clear()


def test_standalone_checklist_without_incident() -> None:
    _clear()
    with TestClient(create_app()) as client:
        created = client.post(
            "/api/checklists",
            json={"name": "Personal Gear Check", "sections": _full_sections()},
            headers=_headers(101),
        )
        assert created.status_code == 201
        doc = created.json()
        assert doc["incident_id"] is None

        response = client.post(
            f"/api/checklists/{doc['id']}/items/chk/responses",
            json={"value": True},
            headers=_headers(101),
        )
        assert response.status_code == 200

        fetched = client.get(f"/api/checklists/{doc['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["status"] == "in_progress"

        progress = client.get(f"/api/checklists/{doc['id']}/progress")
        assert progress.status_code == 200
        assert progress.json()["answered_items"] == 1

        listed = client.get("/api/checklists")
        assert doc["id"] in [row["id"] for row in listed.json()]
    _clear()


def test_linked_record_filter() -> None:
    _clear()
    with TestClient(create_app()) as client:
        linked = _create_blank(
            client, linked_record={"record_type": "planned_event", "record_id": "evt-1"}
        )
        unlinked = _create_blank(client)

        filtered = client.get(
            f"/api/incidents/{INCIDENT_A}/checklists",
            params={"linked_record_type": "planned_event", "linked_record_id": "evt-1"},
        ).json()
        assert [row["id"] for row in filtered] == [linked["id"]]
        assert unlinked["id"] not in [row["id"] for row in filtered]
    _clear()
