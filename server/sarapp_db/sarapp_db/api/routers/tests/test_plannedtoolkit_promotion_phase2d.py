"""Planned Events Toolkit — Phase 2D (Operations Tasking promotion hardening).

Covers the gaps the Phase 0 audit flagged in the existing promotion path
(`promote_quick_assignment` in plannedtoolkit.py): team-assignment forwarding,
the origin-link convention fix (`origin_module`/`origin_id`, matching the
rest of Operations Tasking, instead of the one-off `source_type`/`source_id`
pair the old code wrote), partial-failure recovery via a stable origin
reference, and incident isolation on the promotion endpoint itself.

Basic promotion idempotency, read-only lock-down, and free-text-assignee
round-tripping are already covered by test_plannedtoolkit_assignments.py and
test_plannedtoolkit_repository.py and are not repeated here.
"""
from __future__ import annotations

import os
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db


INCIDENT_ID = "TEST_PLANNED_TOOLKIT_PROMOTION_2D"
OTHER_INCIDENT_ID = "TEST_PLANNED_TOOLKIT_PROMOTION_2D_OTHER"
BASE = f"/api/incidents/{INCIDENT_ID}"
OTHER_BASE = f"/api/incidents/{OTHER_INCIDENT_ID}"


def _clear(incident_id: str) -> None:
    db = get_incident_db(incident_id)
    for collection in (
        IncidentCollections.PLANNED_QUICK_ASSIGNMENTS,
        IncidentCollections.PLANNED_EVENT_SCHEDULES,
        IncidentCollections.OPERATIONS_TASKS,
        IncidentCollections.TEAMS,
    ):
        db[collection].delete_many({})


def setup_function(_fn) -> None:
    _clear(INCIDENT_ID)
    _clear(OTHER_INCIDENT_ID)


def teardown_function(_fn) -> None:
    _clear(INCIDENT_ID)
    _clear(OTHER_INCIDENT_ID)


def test_promotion_forwards_team_assignment():
    """Field-mapping requirement: assigned_team_id must reach the formal
    task via the existing team-assignment service, not be silently dropped."""
    app = create_app()
    with TestClient(app) as client:
        team = client.post(f"{BASE}/operations/teams", json={"name": "Team Alpha"}).json()

        qa = client.post(
            f"{BASE}/planned/quick-assignments",
            json={"title": "Staff checkpoint", "assigned_team_id": str(team["int_id"]), "assigned_to": "Team Alpha"},
        ).json()

        promoted = client.post(f"{BASE}/planned/quick-assignments/{qa['id']}/promote", json={}).json()
        task_id = int(promoted["linked_tasking_id"])

        task_teams = client.get(f"{BASE}/operations/tasks/{task_id}/teams").json()
        assert any(tt["team_id"] == team["int_id"] for tt in task_teams)


def test_promotion_does_not_invent_a_personnel_field_on_the_task():
    """There is no standalone personnel field on a formal task (Operations
    Tasking only tracks personnel through a team's roster) -- a lone
    assigned_person_id must not be silently discarded, but it also must not
    be invented onto the task. It stays visible on the (now read-only)
    source Quick Assignment."""
    app = create_app()
    with TestClient(app) as client:
        qa = client.post(
            f"{BASE}/planned/quick-assignments",
            json={"title": "Radio check", "assigned_person_id": "77", "assigned_to": "J. Rivera"},
        ).json()

        promoted = client.post(f"{BASE}/planned/quick-assignments/{qa['id']}/promote", json={}).json()
        assert promoted["assigned_person_id"] == "77"
        assert promoted["assigned_to"] == "J. Rivera"

        task_id = int(promoted["linked_tasking_id"])
        task = client.get(f"{BASE}/operations/tasks/{task_id}").json()
        assert "assigned_person_id" not in task


def test_promotion_uses_origin_module_and_id_not_a_bespoke_source_pair():
    """The formal task's back-reference to its Quick Assignment must use the
    same origin_module/origin_id convention every other origin-tracked task
    in Operations Tasking uses (see operations.create_task), not a one-off
    source_type/source_id pair nothing else reads."""
    app = create_app()
    with TestClient(app) as client:
        qa = client.post(f"{BASE}/planned/quick-assignments", json={"title": "Open south gate"}).json()
        promoted = client.post(f"{BASE}/planned/quick-assignments/{qa['id']}/promote", json={}).json()
        task_id = int(promoted["linked_tasking_id"])
        task = client.get(f"{BASE}/operations/tasks/{task_id}").json()
        assert task["origin_module"] == "planned_quick_assignment"
        assert task["origin_id"] == qa["record_id"]


def test_promotion_recovers_after_partial_failure_instead_of_duplicating():
    """Simulates a crash between formal-task creation and saving the link
    back onto the Quick Assignment (Phase 2D §5): a formal task already
    exists with the right origin reference, but the source record's
    linked_tasking_id was never written. Retrying promotion must recover
    and link the existing task, never create a second one."""
    app = create_app()
    with TestClient(app) as client:
        qa = client.post(f"{BASE}/planned/quick-assignments", json={"title": "Pre-crashed promotion"}).json()

        # Hand-create the task a crashed first attempt would have left
        # behind: created, origin-linked, but the Quick Assignment update
        # never landed.
        db = get_incident_db(INCIDENT_ID)
        orphan_task = client.post(
            f"{BASE}/operations/tasks",
            json={"title": "Pre-crashed promotion"},
        ).json()
        db[IncidentCollections.OPERATIONS_TASKS].update_one(
            {"int_id": orphan_task["int_id"]},
            {"$set": {
                "origin_module": "planned_quick_assignment",
                "origin_id": qa["record_id"],
                "origin_ref": f"{INCIDENT_ID}:planned_quick_assignment:{qa['record_id']}",
            }},
        )

        recovered = client.post(f"{BASE}/planned/quick-assignments/{qa['id']}/promote", json={}).json()
        assert recovered["linked_tasking_id"] == str(orphan_task["int_id"])

        # Tasks live in a per-incident database already, so no incident_id
        # filter is needed (or available) on the document itself.
        tasks = list(db[IncidentCollections.OPERATIONS_TASKS].find({}))
        assert len(tasks) == 1, "recovery must link the orphaned task, not create a second one"


def test_promotion_respects_incident_isolation():
    """A Quick Assignment belonging to one incident cannot be promoted
    through another incident's URL, and the formal task it produces stays
    scoped to the correct incident."""
    app = create_app()
    with TestClient(app) as client:
        qa = client.post(f"{BASE}/planned/quick-assignments", json={"title": "Incident A assignment"}).json()

        res = client.post(f"{OTHER_BASE}/planned/quick-assignments/{qa['id']}/promote", json={})
        assert res.status_code == 404

        promoted = client.post(f"{BASE}/planned/quick-assignments/{qa['id']}/promote", json={}).json()
        task_id = int(promoted["linked_tasking_id"])
        db = get_incident_db(INCIDENT_ID)
        other_db = get_incident_db(OTHER_INCIDENT_ID)
        assert db[IncidentCollections.OPERATIONS_TASKS].find_one({"int_id": task_id}) is not None
        assert other_db[IncidentCollections.OPERATIONS_TASKS].find_one({"int_id": task_id}) is None


def test_promoting_one_recurring_or_schedule_linked_occurrence_only_affects_that_record():
    """Promotion must not alter the schedule item, a recurrence rule, or any
    sibling assignment -- each Quick Assignment has its own independent
    promotion relationship (Phase 2D §9)."""
    app = create_app()
    with TestClient(app) as client:
        schedule_item = client.post(
            f"{BASE}/planned/promotions/schedule",
            json={"name": "Gate rotation", "starts_at": "2026-12-01T09:00:00"},
        ).json()

        recurring_qa = client.post(
            f"{BASE}/planned/quick-assignments",
            json={
                "title": "Rotate gate staff",
                "recurring": True,
                "recurrence_rule": "FREQ=DAILY",
                "schedule_item_id": schedule_item["record_id"],
            },
        ).json()
        sibling_qa = client.post(
            f"{BASE}/planned/quick-assignments",
            json={"title": "Sibling occurrence", "schedule_item_id": schedule_item["record_id"]},
        ).json()

        promoted = client.post(f"{BASE}/planned/quick-assignments/{recurring_qa['id']}/promote", json={}).json()
        assert promoted["recurring"] is True
        assert promoted["recurrence_rule"] == "FREQ=DAILY"
        assert promoted["schedule_item_id"] == schedule_item["record_id"]

        # The sibling occurrence on the same schedule item is untouched.
        still_unpromoted = client.get(f"{BASE}/planned/quick-assignments").json()
        sibling_after = next(r for r in still_unpromoted if r["id"] == sibling_qa["id"])
        assert sibling_after["linked_tasking_id"] == ""
        assert sibling_after["promoted_read_only"] is False

        # The schedule item itself is untouched by the sibling's promotion.
        schedule_after = client.get(f"{BASE}/planned/promotions/schedule").json()[0]
        assert schedule_after["title"] == "Gate rotation"


def test_promotion_from_schedule_triggered_assignment_preserves_source_link():
    """A Quick Assignment auto-created from a schedule activity (Phase 1D's
    create-quick-assignment endpoint) keeps its own source_type/source_id
    pointing back at the schedule item after promotion -- promotion only
    ever adds the linked_tasking_id/promoted_* fields, never clears an
    existing source link."""
    app = create_app()
    with TestClient(app) as client:
        schedule_item = client.post(
            f"{BASE}/planned/promotions/schedule",
            json={"name": "Opening Briefing", "starts_at": "2026-12-01T09:00:00"},
        ).json()

        created = client.post(
            f"{BASE}/planned/promotions/schedule/{schedule_item['id']}/create-quick-assignment"
        ).json()
        qa = created["quick_assignment"]
        assert qa["source_type"] == "planned_schedule_item"

        promoted = client.post(f"{BASE}/planned/quick-assignments/{qa['id']}/promote", json={}).json()
        assert promoted["source_type"] == "planned_schedule_item"
        assert promoted["source_id"] == schedule_item["record_id"]
        assert promoted["linked_tasking_id"]


def test_origin_ref_is_enforced_at_the_database_level_not_just_in_application_code():
    """Phase 2D §4: 'a simple check for an existing task before creating
    another is not sufficient for concurrency safety.' Proves the sparse
    unique index on tasks.origin_ref is what actually makes two
    simultaneous first-time creation attempts for the same source record
    impossible at the database layer, independent of promote_quick_assignment's
    own look-before-create logic."""
    from pymongo.errors import DuplicateKeyError

    from sarapp_db.api.routers.operations import create_task
    from sarapp_db.mongo.errors import RepositoryError
    from sarapp_db.mongo.indexes import ensure_task_origin_ref_index

    db = get_incident_db(INCIDENT_ID)
    ensure_task_origin_ref_index(db)

    body = {"title": "Race winner", "origin_module": "planned_quick_assignment", "origin_id": "QA-RACE-1"}
    create_task(INCIDENT_ID, dict(body))

    try:
        create_task(INCIDENT_ID, dict(body, title="Race loser"))
        raise AssertionError("a second task with the same origin_ref must be rejected at the database level")
    except RepositoryError as exc:
        assert isinstance(exc.__cause__, DuplicateKeyError)

    assert db[IncidentCollections.OPERATIONS_TASKS].count_documents({"origin_id": "QA-RACE-1"}) == 1


def test_ordinary_task_creation_is_unaffected_by_the_origin_ref_index():
    """Existing Operations Tasking functionality: creating ordinary tasks
    with no origin reference (the overwhelming majority of tasks) must keep
    working freely, with no collision from the new sparse unique index on
    origin_ref -- that field is only ever set on promotion-created tasks."""
    app = create_app()
    with TestClient(app) as client:
        first = client.post(f"{BASE}/operations/tasks", json={"title": "Ordinary task one"})
        second = client.post(f"{BASE}/operations/tasks", json={"title": "Ordinary task two"})
        assert first.status_code == 201, first.text
        assert second.status_code == 201, second.text
        assert "origin_ref" not in first.json()
        assert "origin_ref" not in second.json()
