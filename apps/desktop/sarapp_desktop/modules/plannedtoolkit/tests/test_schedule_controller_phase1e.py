"""Phase 1E: controller-level reliability behaviors.

- A transient refresh failure must not wipe what's already displayed
  (the brief's "temporary connection failures do not destroy the
  displayed schedule").
- A 409 conflict from any mutation triggers an immediate resync so the
  caller's next read reflects the server's real current state (the
  brief's "allow the user to reload").
"""
from __future__ import annotations

from utils.api_client import APIError

import modules.plannedtoolkit.services as services
from modules.plannedtoolkit.records import ScheduledItem
from modules.plannedtoolkit.schedule_controller import ScheduleController


def test_refresh_failure_preserves_last_known_good_items(monkeypatch) -> None:
    good_items = [ScheduledItem(id=1, name="A", starts_at="2026-12-01T09:00:00")]
    monkeypatch.setattr(services, "list_schedule_items", lambda incident_id=None: good_items)
    ctrl = ScheduleController("INC1")
    assert len(ctrl.items()) == 1

    def boom(incident_id=None):
        raise APIError("disconnected", status_code=None)

    monkeypatch.setattr(services, "list_schedule_items", boom)
    messages = []
    ctrl.statusMessage.connect(lambda m, e: messages.append((m, e)))
    ctrl.refresh()

    # Still showing the last known-good data, not wiped to empty.
    assert len(ctrl.items()) == 1
    assert ctrl.items()[0].name == "A"
    assert messages[-1][1] is True


def test_refresh_recovers_once_connection_returns(monkeypatch) -> None:
    good_items = [ScheduledItem(id=1, name="A")]
    monkeypatch.setattr(services, "list_schedule_items", lambda incident_id=None: good_items)
    ctrl = ScheduleController("INC1")

    def boom(incident_id=None):
        raise APIError("disconnected", status_code=None)

    monkeypatch.setattr(services, "list_schedule_items", boom)
    ctrl.refresh()
    assert len(ctrl.items()) == 1  # preserved through the outage

    updated_items = [ScheduledItem(id=1, name="A"), ScheduledItem(id=2, name="B")]
    monkeypatch.setattr(services, "list_schedule_items", lambda incident_id=None: updated_items)
    ctrl.refresh()
    assert len(ctrl.items()) == 2  # caught up once reachable again


def test_conflict_triggers_immediate_resync(monkeypatch) -> None:
    stale_items = [ScheduledItem(id=1, name="Stale view", revision=0)]
    monkeypatch.setattr(services, "list_schedule_items", lambda incident_id=None: stale_items)
    ctrl = ScheduleController("INC1")

    def conflict(rid, incident_id=None, **kw):
        raise APIError("conflict", status_code=409)

    monkeypatch.setattr(services, "start_schedule_item", conflict)

    refreshed_items = [ScheduledItem(id=1, name="Current view", revision=1)]
    monkeypatch.setattr(services, "list_schedule_items", lambda incident_id=None: refreshed_items)

    conflicts = []
    ctrl.conflict.connect(lambda m: conflicts.append(m))
    ok = ctrl.start(1, expected_revision=0)

    assert ok is False
    assert len(conflicts) == 1
    # The controller resynced to the server's current state after the conflict.
    assert ctrl.items()[0].name == "Current view"
    assert ctrl.items()[0].revision == 1


def test_non_conflict_failure_does_not_trigger_resync(monkeypatch) -> None:
    items = [ScheduledItem(id=1, name="A")]
    refresh_calls = {"n": 0}

    def list_items(incident_id=None):
        refresh_calls["n"] += 1
        return items

    monkeypatch.setattr(services, "list_schedule_items", list_items)
    ctrl = ScheduleController("INC1")
    baseline = refresh_calls["n"]

    def server_error(rid, incident_id=None, **kw):
        raise APIError("internal error", status_code=500)

    monkeypatch.setattr(services, "start_schedule_item", server_error)
    conflicts = []
    ctrl.conflict.connect(lambda m: conflicts.append(m))
    ok = ctrl.start(1, expected_revision=0)

    assert ok is False
    assert conflicts == []
    assert refresh_calls["n"] == baseline  # no extra resync for a non-conflict error
