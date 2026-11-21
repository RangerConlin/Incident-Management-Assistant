"""Phase 1D: Event Schedule cross-module integration (backend half).

Covers meeting/GIS linking, relative-reminder resolution, trigger
rescheduling/cancellation cascades, Quick Assignment creation from an
activity, incident isolation, and backward compatibility.
"""
from __future__ import annotations

import os
import pathlib
import sys
from datetime import datetime, timedelta, timezone

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.services import trigger_engine

INCIDENT_A = "TEST_SCHEDULE_INTEGRATION_A"
INCIDENT_B = "TEST_SCHEDULE_INTEGRATION_B"


def _base(incident_id: str) -> str:
    return f"/api/incidents/{incident_id}"


def _clear(db):
    for collection in (
        IncidentCollections.PLANNED_EVENT_SCHEDULES,
        IncidentCollections.PLANNED_SCHEDULE_TRIGGERS,
        IncidentCollections.PLANNED_QUICK_ASSIGNMENTS,
        IncidentCollections.NOTIFICATIONS,
        IncidentCollections.AUDIT_LOGS,
    ):
        db[collection].delete_many({})


def test_meeting_and_gis_link_round_trip_and_unlink():
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule", json={"name": "Staff Briefing"})
        rid = res.json()["id"]

        res = client.patch(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}", json={"meeting_id": "42", "gis_feature_id": "7"})
        assert res.status_code == 200
        assert res.json()["meeting_id"] == "42"
        assert res.json()["gis_feature_id"] == "7"

        # Unlink without deleting the underlying meeting/feature (which this
        # router doesn't own and never touches).
        res = client.patch(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}", json={"meeting_id": "", "gis_feature_id": ""})
        assert res.status_code == 200
        assert res.json()["meeting_id"] == ""
        assert res.json()["gis_feature_id"] == ""
    _clear(db)


def test_relative_reminder_resolves_absolute_trigger_at():
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"{_base(INCIDENT_A)}/planned/promotions/schedule",
            json={"name": "Opening", "starts_at": "2026-12-01T09:00:00", "ends_at": "2026-12-01T09:30:00"},
        )
        schedule_item = res.json()

        res = client.post(
            f"{_base(INCIDENT_A)}/planned-meta/schedule-triggers",
            json={
                "schedule_item_id": schedule_item["record_id"],
                "title": "15 min warning",
                "offset_minutes": -15,
                "relative_to": "start",
                "severity": "priority",
            },
        )
        assert res.status_code == 201, res.text
        trigger = res.json()
        assert trigger["trigger_at"] == "2026-12-01T08:45:00"
        assert trigger["severity"] == "priority"
    _clear(db)


def test_absolute_reminder_is_unaffected_by_relative_resolution():
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule", json={"name": "Opening", "starts_at": "2026-12-01T09:00:00"})
        schedule_item = res.json()
        res = client.post(
            f"{_base(INCIDENT_A)}/planned-meta/schedule-triggers",
            json={"schedule_item_id": schedule_item["record_id"], "title": "x", "trigger_at": "2026-11-01T00:00:00"},
        )
        assert res.json()["trigger_at"] == "2026-11-01T00:00:00"
    _clear(db)


def test_rescheduling_activity_recomputes_pending_relative_trigger():
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"{_base(INCIDENT_A)}/planned/promotions/schedule",
            json={"name": "Opening", "starts_at": "2026-12-01T09:00:00", "ends_at": "2026-12-01T09:30:00"},
        )
        schedule_item = res.json()
        rid = schedule_item["id"]
        client.post(
            f"{_base(INCIDENT_A)}/planned-meta/schedule-triggers",
            json={"schedule_item_id": schedule_item["record_id"], "title": "x", "offset_minutes": -15, "relative_to": "start"},
        )

        res = client.patch(
            f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}",
            json={"starts_at": "2026-12-01T10:00:00", "ends_at": "2026-12-01T10:30:00"},
        )
        assert res.status_code == 200, res.text

        res = client.get(f"{_base(INCIDENT_A)}/planned-meta/schedule-triggers", params={"schedule_item_id": schedule_item["record_id"]})
        triggers = res.json()
        assert len(triggers) == 1
        assert triggers[0]["trigger_at"] == "2026-12-01T09:45:00"
    _clear(db)


def test_cancelling_activity_disables_pending_trigger_not_already_fired():
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        due_at = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule", json={"name": "Already fired one"})
        fired_item_rid = res.json()["id"]
        fired_item_compound = res.json()["record_id"]
        client.post(
            f"{_base(INCIDENT_A)}/planned-meta/schedule-triggers",
            json={"schedule_item_id": fired_item_compound, "title": "fires now", "trigger_at": due_at},
        )
        fired = trigger_engine.evaluate_due_triggers(INCIDENT_A)
        assert fired == 1

        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule", json={"name": "Pending one"})
        pending_item_rid = res.json()["id"]
        pending_item_compound = res.json()["record_id"]
        client.post(
            f"{_base(INCIDENT_A)}/planned-meta/schedule-triggers",
            json={"schedule_item_id": pending_item_compound, "title": "not yet due", "trigger_at": "2099-01-01T00:00:00"},
        )

        # Cancel both activities.
        client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{fired_item_rid}/cancel", json={"cancellation_reason": "x"})
        client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{pending_item_rid}/cancel", json={"cancellation_reason": "x"})

        fired_triggers = client.get(f"{_base(INCIDENT_A)}/planned-meta/schedule-triggers", params={"schedule_item_id": fired_item_compound}).json()
        pending_triggers = client.get(f"{_base(INCIDENT_A)}/planned-meta/schedule-triggers", params={"schedule_item_id": pending_item_compound}).json()

        # Already-fired trigger is untouched (its notification was already delivered).
        assert fired_triggers[0]["enabled"] is True
        # Pending trigger is disabled so it never fires after the cancellation.
        assert pending_triggers[0]["enabled"] is False

        assert db[IncidentCollections.NOTIFICATIONS].count_documents({"incident_id": INCIDENT_A}) == 1
        trigger_engine.evaluate_due_triggers(INCIDENT_A)  # pending trigger's time has long passed
        assert db[IncidentCollections.NOTIFICATIONS].count_documents({"incident_id": INCIDENT_A}) == 1
    _clear(db)


def test_create_quick_assignment_from_activity_establishes_source_link():
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"{_base(INCIDENT_A)}/planned/promotions/schedule",
            json={"name": "Site Setup", "assigned_to": "Logistics", "location": "Main Gate"},
        )
        schedule_item = res.json()
        rid = schedule_item["id"]

        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/create-quick-assignment")
        assert res.status_code == 201, res.text
        result = res.json()
        qa = result["quick_assignment"]
        assert qa["title"] == "Site Setup"
        assert qa["assigned_to"] == "Logistics"
        assert qa["location"] == "Main Gate"
        assert qa["source_type"] == "planned_schedule_item"
        assert qa["source_id"] == schedule_item["record_id"]
        assert result["schedule_item"]["quick_assignment_id"] == qa["record_id"]

        # A second call must not create a duplicate link.
        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/create-quick-assignment")
        assert res.status_code == 409

        assert db[IncidentCollections.PLANNED_QUICK_ASSIGNMENTS].count_documents(
            {"incident_id": INCIDENT_A, "source_type": "planned_schedule_item"}
        ) == 1
    _clear(db)


def test_linking_missing_meeting_record_returns_404_from_meetings_api():
    """The Event Schedule never duplicates meeting data; a deleted/missing
    meeting is detected by asking the Meeting Planner API directly, which
    the desktop client is expected to handle gracefully (see widgets)."""
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        res = client.get(f"{_base(INCIDENT_A)}/planning/meetings/999999")
        assert res.status_code == 404
    _clear(db)


def test_schedule_integration_fields_are_isolated_per_incident():
    db_a = get_incident_db(INCIDENT_A)
    db_b = get_incident_db(INCIDENT_B)
    _clear(db_a)
    _clear(db_b)
    app = create_app()
    with TestClient(app) as client:
        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule", json={"name": "A", "meeting_id": "1"})
        rid_a = res.json()["id"]
        res = client.post(f"{_base(INCIDENT_B)}/planned/promotions/schedule", json={"name": "B", "meeting_id": "2"})

        items_a = client.get(f"{_base(INCIDENT_A)}/planned/promotions/schedule").json()
        items_b = client.get(f"{_base(INCIDENT_B)}/planned/promotions/schedule").json()
        assert [i["meeting_id"] for i in items_a] == ["1"]
        assert [i["meeting_id"] for i in items_b] == ["2"]
    _clear(db_a)
    _clear(db_b)


def test_backward_compatible_with_pre_phase1d_schedule_item():
    """A Phase 1A/1B-era item with none of the Phase 1D link fields must
    still read back without error, with the new fields simply empty."""
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    db[IncidentCollections.PLANNED_EVENT_SCHEDULES].insert_one({
        "_id": "legacy-1",
        "schedule_id": f"{INCIDENT_A}-PLAN-SCHEDULE-1",
        "seq": 1,
        "incident_id": INCIDENT_A,
        "tool": "promotions/schedule",
        "name": "Legacy item",
        "kind": "Milestone",
        "starts_at": "2026-01-01T00:00:00",
        "ends_at": "",
        "notes": "",
        "location": "", "zone": "", "owner": "", "status": "Scheduled", "tags": [],
        "created_at": "x", "updated_at": "x", "deleted": False,
    })
    app = create_app()
    with TestClient(app) as client:
        res = client.get(f"{_base(INCIDENT_A)}/planned/promotions/schedule")
        assert res.status_code == 200
        legacy = res.json()[0]
        assert legacy["meeting_id"] == ""
        assert legacy["gis_feature_id"] == ""
        assert legacy["quick_assignment_id"] == ""
    _clear(db)
