"""Phase 1C: the shared ScheduleController the Timeline and Activity List
views both read from. Every mutation here must delegate to `services.py`
(the same calls Phase 1A/1B's backend validates) rather than implement any
status-changing logic locally.
"""
from __future__ import annotations

from utils.api_client import APIError
from utils.incident_cache import incident_cache

import modules.plannedtoolkit.services as services
from modules.plannedtoolkit.records import ScheduledItem
from modules.plannedtoolkit.schedule_controller import ScheduleController


def _item(id_=1, name="A", starts_at="2026-12-01T09:00:00", status="Scheduled") -> ScheduledItem:
    return ScheduledItem(id=id_, name=name, starts_at=starts_at, status=status)


def test_refresh_with_no_incident_is_empty_and_reports_status(monkeypatch) -> None:
    ctrl = ScheduleController(None)
    messages = []
    ctrl.statusMessage.connect(lambda m, e: messages.append((m, e)))
    ctrl.refresh()
    assert ctrl.items() == []
    assert messages[-1][1] is True


def test_refresh_sorts_items_chronologically(monkeypatch) -> None:
    rows = [
        _item(1, "Later", "2026-12-01T11:00:00"),
        _item(2, "Earlier", "2026-12-01T09:00:00"),
    ]
    monkeypatch.setattr(services, "list_schedule_items", lambda incident_id=None: rows)
    ctrl = ScheduleController("INC1")
    names = [item.name for item in ctrl.items()]
    assert names == ["Earlier", "Later"]


def test_refresh_handles_empty_schedule(monkeypatch) -> None:
    monkeypatch.setattr(services, "list_schedule_items", lambda incident_id=None: [])
    ctrl = ScheduleController("INC1")
    assert ctrl.items() == []


def test_api_error_surfaces_as_status_message_and_empty_items(monkeypatch) -> None:
    def boom(incident_id=None):
        raise APIError("down", status_code=503)

    monkeypatch.setattr(services, "list_schedule_items", boom)
    ctrl = ScheduleController("INC1")
    messages = []
    ctrl.statusMessage.connect(lambda m, e: messages.append((m, e)))
    ctrl.refresh()
    assert ctrl.items() == []
    assert messages[-1][1] is True
    assert "503" in messages[-1][0]


def test_cancelled_items_remain_visible_in_items_list(monkeypatch) -> None:
    rows = [_item(1, "Cancelled one", status="Cancelled")]
    monkeypatch.setattr(services, "list_schedule_items", lambda incident_id=None: rows)
    ctrl = ScheduleController("INC1")
    assert [item.status for item in ctrl.items()] == ["Cancelled"]


def test_mutations_delegate_to_shared_services_not_local_logic(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(services, "list_schedule_items", lambda incident_id=None: [])
    monkeypatch.setattr(services, "create_schedule_item", lambda incident_id=None, **kw: calls.append(("create", kw)))
    monkeypatch.setattr(services, "update_schedule_item", lambda rid, patch, incident_id=None: calls.append(("update", rid, patch)))
    monkeypatch.setattr(services, "delete_schedule_item", lambda rid, incident_id=None: calls.append(("delete", rid)))
    monkeypatch.setattr(services, "start_schedule_item", lambda rid, incident_id=None: calls.append(("start", rid)))
    monkeypatch.setattr(services, "resume_schedule_item", lambda rid, incident_id=None: calls.append(("resume", rid)))
    monkeypatch.setattr(services, "complete_schedule_item", lambda rid, incident_id=None: calls.append(("complete", rid)))
    monkeypatch.setattr(
        services, "delay_schedule_item",
        lambda rid, incident_id=None, *, delay_reason: calls.append(("delay", rid, delay_reason)),
    )
    monkeypatch.setattr(
        services, "cancel_schedule_item",
        lambda rid, incident_id=None, *, cancellation_reason: calls.append(("cancel", rid, cancellation_reason)),
    )

    ctrl = ScheduleController("INC1")
    ctrl.create(name="New")
    ctrl.update(1, {"location": "Tent"})
    ctrl.delete(1)
    ctrl.start(1)
    ctrl.resume(1)
    ctrl.complete(1)
    ctrl.delay(1, delay_reason="weather")
    ctrl.cancel(1, cancellation_reason="storm")

    assert ("create", {"name": "New"}) in calls
    assert ("update", 1, {"location": "Tent"}) in calls
    assert ("delete", 1) in calls
    assert ("start", 1) in calls
    assert ("resume", 1) in calls
    assert ("complete", 1) in calls
    assert ("delay", 1, "weather") in calls
    assert ("cancel", 1, "storm") in calls


def test_action_failure_reports_status_and_does_not_raise(monkeypatch) -> None:
    monkeypatch.setattr(services, "list_schedule_items", lambda incident_id=None: [])

    def boom(rid, incident_id=None):
        raise APIError("conflict", status_code=409)

    monkeypatch.setattr(services, "start_schedule_item", boom)
    ctrl = ScheduleController("INC1")
    messages = []
    ctrl.statusMessage.connect(lambda m, e: messages.append((m, e)))
    ok = ctrl.start(1)
    assert ok is False
    assert messages[-1][1] is True
    assert "409" in messages[-1][0]


def test_live_update_refreshes_only_for_schedule_collection(monkeypatch) -> None:
    monkeypatch.setattr(services, "list_schedule_items", lambda incident_id=None: [])
    # A QObject with no Qt parent (as here) stays connected to the
    # incident_cache singleton for the rest of the process, so count this
    # controller's own itemsChanged emissions rather than a global call
    # counter other tests' leftover controllers would also bump.
    ctrl = ScheduleController("INC1")
    hits = []
    ctrl.itemsChanged.connect(lambda: hits.append(1))

    incident_cache.apply_event({"collection": "planned_event_schedules", "op": "updated", "id": "x", "doc": {}})
    assert len(hits) == 1

    incident_cache.apply_event({"collection": "some_other_collection", "op": "updated", "id": "y", "doc": {}})
    assert len(hits) == 1
