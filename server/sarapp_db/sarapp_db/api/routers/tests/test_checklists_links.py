"""Phase 4D: checklist <-> planned-event record associations
(linked_records), incident-scoped validation, and the Assignment ->
Operations Task promotion propagation."""
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

INCIDENT_A = "TEST_CHECKLISTS_LINKS_A"
INCIDENT_B = "TEST_CHECKLISTS_LINKS_B"


def _headers(person_record: int) -> dict[str, str]:
    token = _issue_jwt({"sub": f"user-{person_record}", "person_record": person_record})
    return {"Authorization": f"Bearer {token}"}


def _clear() -> None:
    for incident_id in (INCIDENT_A, INCIDENT_B):
        db = get_incident_db(incident_id)
        for collection in (
            IncidentCollections.CHECKLISTS,
            IncidentCollections.PLANNED_EVENT_SCHEDULES,
            IncidentCollections.PLANNED_QUICK_ASSIGNMENTS,
            IncidentCollections.OPERATIONS_TASKS,
        ):
            db[collection].delete_many({})
    get_master_db()[MasterCollections.CHECKLISTS].delete_many({})


def _create_checklist(client: TestClient, incident_id: str = INCIDENT_A, **overrides) -> dict:
    body = {
        "name": "Equipment Check",
        "sections": [{"id": "s1", "name": "A", "items": [{"id": "i1", "item_type": "checkbox", "label": "x"}]}],
        **overrides,
    }
    response = client.post(f"/api/incidents/{incident_id}/checklists", json=body, headers=_headers(101))
    assert response.status_code == 201, response.text
    return response.json()


def _create_schedule_item(client: TestClient, incident_id: str = INCIDENT_A, **overrides) -> dict:
    body = {"name": "Opening Ceremony", "kind": "Milestone", "starts_at": "2026-01-01T09:00:00", **overrides}
    response = client.post(f"/api/incidents/{incident_id}/planned/promotions/schedule", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _create_assignment(client: TestClient, incident_id: str = INCIDENT_A, **overrides) -> dict:
    body = {"title": "Staff water station", "priority": "Low", **overrides}
    response = client.post(f"/api/incidents/{incident_id}/planned/quick-assignments", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _link(client, incident_id, checklist_id, record_type, record_id, actor=101):
    return client.post(
        f"/api/incidents/{incident_id}/checklists/{checklist_id}/links",
        json={"record_type": record_type, "record_id": record_id},
        headers=_headers(actor),
    )


def _unlink(client, incident_id, checklist_id, record_type, record_id, actor=101):
    return client.post(
        f"/api/incidents/{incident_id}/checklists/{checklist_id}/links/remove",
        json={"record_type": record_type, "record_id": record_id},
        headers=_headers(actor),
    )


# ---------------------------------------------------------------------------
# Association tests
# ---------------------------------------------------------------------------

def test_link_existing_checklist_to_schedule_item() -> None:
    _clear()
    with TestClient(create_app()) as client:
        checklist = _create_checklist(client)
        schedule_item = _create_schedule_item(client)

        response = _link(client, INCIDENT_A, checklist["id"], "planned_schedule_item", schedule_item["record_id"])
        assert response.status_code == 201, response.text
        assert response.json()["linked_records"] == [
            {"record_type": "planned_schedule_item", "record_id": schedule_item["record_id"]}
        ]

        filtered = client.get(
            f"/api/incidents/{INCIDENT_A}/checklists",
            params={"linked_record_type": "planned_schedule_item", "linked_record_id": schedule_item["record_id"]},
        ).json()
        assert [c["id"] for c in filtered] == [checklist["id"]]
    _clear()


def test_link_existing_checklist_to_assignment() -> None:
    _clear()
    with TestClient(create_app()) as client:
        checklist = _create_checklist(client)
        assignment = _create_assignment(client)

        response = _link(client, INCIDENT_A, checklist["id"], "planned_quick_assignment", assignment["record_id"])
        assert response.status_code == 201, response.text
    _clear()


def test_create_checklist_directly_from_record_with_initial_link() -> None:
    _clear()
    with TestClient(create_app()) as client:
        assignment = _create_assignment(client)
        checklist = _create_checklist(
            client,
            linked_records=[{"record_type": "planned_quick_assignment", "record_id": assignment["record_id"]}],
        )
        assert checklist["linked_records"] == [
            {"record_type": "planned_quick_assignment", "record_id": assignment["record_id"]}
        ]
    _clear()


def test_one_checklist_linked_to_multiple_records() -> None:
    _clear()
    with TestClient(create_app()) as client:
        checklist = _create_checklist(client)
        schedule_item = _create_schedule_item(client)
        assignment = _create_assignment(client)

        _link(client, INCIDENT_A, checklist["id"], "planned_schedule_item", schedule_item["record_id"])
        response = _link(client, INCIDENT_A, checklist["id"], "planned_quick_assignment", assignment["record_id"])
        assert response.status_code == 201
        assert len(response.json()["linked_records"]) == 2
    _clear()


def test_multiple_checklists_linked_to_one_record() -> None:
    _clear()
    with TestClient(create_app()) as client:
        schedule_item = _create_schedule_item(client)
        checklist_a = _create_checklist(client, name="Checklist A")
        checklist_b = _create_checklist(client, name="Checklist B")

        _link(client, INCIDENT_A, checklist_a["id"], "planned_schedule_item", schedule_item["record_id"])
        _link(client, INCIDENT_A, checklist_b["id"], "planned_schedule_item", schedule_item["record_id"])

        filtered = client.get(
            f"/api/incidents/{INCIDENT_A}/checklists",
            params={"linked_record_type": "planned_schedule_item", "linked_record_id": schedule_item["record_id"]},
        ).json()
        assert {c["id"] for c in filtered} == {checklist_a["id"], checklist_b["id"]}
    _clear()


def test_remove_association_preserves_checklist_and_history() -> None:
    _clear()
    with TestClient(create_app()) as client:
        checklist = _create_checklist(client)
        schedule_item = _create_schedule_item(client)
        _link(client, INCIDENT_A, checklist["id"], "planned_schedule_item", schedule_item["record_id"])

        client.post(
            f"/api/incidents/{INCIDENT_A}/checklists/{checklist['id']}/items/i1/responses",
            json={"value": True},
            headers=_headers(101),
        )

        response = _unlink(client, INCIDENT_A, checklist["id"], "planned_schedule_item", schedule_item["record_id"])
        assert response.status_code == 200
        assert response.json()["linked_records"] == []

        reloaded = client.get(f"/api/incidents/{INCIDENT_A}/checklists/{checklist['id']}").json()
        assert reloaded["status"] == "in_progress"  # checklist itself preserved
        item = next(i for i in reloaded["sections"][0]["items"] if i["id"] == "i1")
        assert item["response"]["value"] is True  # response history preserved
    _clear()


def test_removing_one_association_preserves_others() -> None:
    _clear()
    with TestClient(create_app()) as client:
        checklist = _create_checklist(client)
        schedule_item = _create_schedule_item(client)
        assignment = _create_assignment(client)
        _link(client, INCIDENT_A, checklist["id"], "planned_schedule_item", schedule_item["record_id"])
        _link(client, INCIDENT_A, checklist["id"], "planned_quick_assignment", assignment["record_id"])

        response = _unlink(client, INCIDENT_A, checklist["id"], "planned_schedule_item", schedule_item["record_id"])
        assert response.json()["linked_records"] == [
            {"record_type": "planned_quick_assignment", "record_id": assignment["record_id"]}
        ]
    _clear()


def test_duplicate_association_rejected() -> None:
    _clear()
    with TestClient(create_app()) as client:
        checklist = _create_checklist(client)
        schedule_item = _create_schedule_item(client)
        first = _link(client, INCIDENT_A, checklist["id"], "planned_schedule_item", schedule_item["record_id"])
        assert first.status_code == 201
        second = _link(client, INCIDENT_A, checklist["id"], "planned_schedule_item", schedule_item["record_id"])
        assert second.status_code == 409
    _clear()


def test_cross_incident_association_rejected() -> None:
    _clear()
    with TestClient(create_app()) as client:
        checklist = _create_checklist(client, incident_id=INCIDENT_A)
        schedule_item_in_b = _create_schedule_item(client, incident_id=INCIDENT_B)

        response = _link(
            client, INCIDENT_A, checklist["id"], "planned_schedule_item", schedule_item_in_b["record_id"]
        )
        assert response.status_code == 422
    _clear()


def test_nonexistent_target_record_rejected() -> None:
    _clear()
    with TestClient(create_app()) as client:
        checklist = _create_checklist(client)
        response = _link(client, INCIDENT_A, checklist["id"], "planned_schedule_item", "999999")
        assert response.status_code == 422
    _clear()


def test_unknown_record_type_rejected() -> None:
    _clear()
    with TestClient(create_app()) as client:
        checklist = _create_checklist(client)
        response = _link(client, INCIDENT_A, checklist["id"], "not_a_real_type", "1")
        assert response.status_code == 422
    _clear()


def test_unauthorized_association_change_rejected() -> None:
    _clear()
    with TestClient(create_app()) as client:
        checklist = _create_checklist(client)
        schedule_item = _create_schedule_item(client)
        response = client.post(
            f"/api/incidents/{INCIDENT_A}/checklists/{checklist['id']}/links",
            json={"record_type": "planned_schedule_item", "record_id": schedule_item["record_id"]},
        )  # no Authorization header, no session_id
        assert response.status_code == 401
    _clear()


def test_standalone_checklist_cannot_link_incident_record() -> None:
    _clear()
    with TestClient(create_app()) as client:
        standalone = client.post(
            "/api/checklists",
            json={
                "name": "Personal",
                "sections": [{"id": "s1", "items": [{"id": "i1", "item_type": "checkbox", "label": "x"}]}],
            },
            headers=_headers(101),
        ).json()
        schedule_item = _create_schedule_item(client)

        response = client.post(
            f"/api/checklists/{standalone['id']}/links",
            json={"record_type": "planned_schedule_item", "record_id": schedule_item["record_id"]},
            headers=_headers(101),
        )
        assert response.status_code == 400

        create_with_link = client.post(
            "/api/checklists",
            json={
                "name": "Personal 2",
                "sections": [{"id": "s1", "items": [{"id": "i1", "item_type": "checkbox", "label": "x"}]}],
                "linked_records": [{"record_type": "planned_schedule_item", "record_id": schedule_item["record_id"]}],
            },
            headers=_headers(101),
        )
        assert create_with_link.status_code == 400
    _clear()


# ---------------------------------------------------------------------------
# Promotion tests
# ---------------------------------------------------------------------------

def test_promotion_propagates_checklist_link_without_duplicating() -> None:
    _clear()
    with TestClient(create_app()) as client:
        assignment = _create_assignment(client)
        checklist = _create_checklist(client)
        _link(client, INCIDENT_A, checklist["id"], "planned_quick_assignment", assignment["record_id"])

        # Answer an item so we can confirm promotion never touches responses.
        client.post(
            f"/api/incidents/{INCIDENT_A}/checklists/{checklist['id']}/items/i1/responses",
            json={"value": True},
            headers=_headers(101),
        )

        promoted = client.post(
            f"/api/incidents/{INCIDENT_A}/planned/quick-assignments/{assignment['id']}/promote",
            json={"promoted_by": "planner"},
        )
        assert promoted.status_code == 200
        task_id = promoted.json()["linked_tasking_id"]
        assert task_id

        reloaded = client.get(f"/api/incidents/{INCIDENT_A}/checklists/{checklist['id']}").json()
        record_types = {link["record_type"] for link in reloaded["linked_records"]}
        assert record_types == {"planned_quick_assignment", "operations_task"}
        # The originating Assignment association survives promotion.
        assert any(
            link["record_type"] == "planned_quick_assignment" and link["record_id"] == assignment["record_id"]
            for link in reloaded["linked_records"]
        )
        # Response history untouched by promotion.
        item = next(i for i in reloaded["sections"][0]["items"] if i["id"] == "i1")
        assert item["response"]["value"] is True

        # Exactly one checklist instance exists -- promotion never duplicates it.
        all_checklists = client.get(f"/api/incidents/{INCIDENT_A}/checklists").json()
        assert len(all_checklists) == 1

    _clear()


def test_promotion_retry_does_not_duplicate_association_or_task() -> None:
    _clear()
    with TestClient(create_app()) as client:
        assignment = _create_assignment(client)
        checklist = _create_checklist(client)
        _link(client, INCIDENT_A, checklist["id"], "planned_quick_assignment", assignment["record_id"])

        first = client.post(
            f"/api/incidents/{INCIDENT_A}/planned/quick-assignments/{assignment['id']}/promote",
            json={"promoted_by": "planner"},
        )
        second = client.post(
            f"/api/incidents/{INCIDENT_A}/planned/quick-assignments/{assignment['id']}/promote",
            json={"promoted_by": "planner-retry"},
        )
        assert first.json()["linked_tasking_id"] == second.json()["linked_tasking_id"]

        reloaded = client.get(f"/api/incidents/{INCIDENT_A}/checklists/{checklist['id']}").json()
        assert len(reloaded["linked_records"]) == 2  # not 3 or 4 after the retry

        task_docs = list(get_incident_db(INCIDENT_A)[IncidentCollections.OPERATIONS_TASKS].find({}))
        assert len(task_docs) == 1
    _clear()


def test_promotion_without_a_linked_checklist_is_a_silent_no_op() -> None:
    _clear()
    with TestClient(create_app()) as client:
        assignment = _create_assignment(client)
        response = client.post(
            f"/api/incidents/{INCIDENT_A}/planned/quick-assignments/{assignment['id']}/promote",
            json={"promoted_by": "planner"},
        )
        assert response.status_code == 200
        assert response.json()["linked_tasking_id"]
    _clear()
