from __future__ import annotations

import importlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from utils import state as app_state
import modules.logistics.checkin.exceptions as checkin_exceptions


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _setup_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHECKIN_DATA_DIR", str(tmp_path))
    # Reload helpers so they pick up the new data directory
    import utils.incident_context as incident_context
    import utils.db as db
    import modules.logistics.checkin.schema as schema
    import modules.logistics.checkin.repository as repository
    import modules.logistics.checkin.services as services

    importlib.reload(incident_context)
    importlib.reload(db)
    importlib.reload(schema)
    importlib.reload(repository)
    importlib.reload(services)

    # Reset module level service
    services._service = services.CheckInService(
        queue_store=services.QueueStore(tmp_path / "queue.json")
    )
    incident_context.set_active_incident("INC-1")
    app_state.AppState.set_active_incident("INC-1")
    app_state.AppState.set_active_user_id("user-1")
    app_state.AppState.set_active_user_role("Logistics")
    return services, schema


def _seed_personnel(tmp_path: Path, schema) -> None:
    with sqlite3.connect(tmp_path / "master.db") as conn:
        schema.ensure_master_schema(conn)
        conn.executemany(
            "INSERT INTO personnel (id, name, primary_role, phone, callsign, certifications, home_unit) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("P1", "Alice Smith", "Medic", "555-1111", "ALPHA", "EMT", "UnitA"),
                ("P2", "Bob Jones", "Ground", "555-2222", "BRAVO", "SAR", "UnitB"),
            ],
        )
        conn.commit()


@pytest.fixture()
def services_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    services, schema = _setup_environment(tmp_path, monkeypatch)
    _seed_personnel(tmp_path, schema)
    return services


def test_checked_in_without_team_sets_available(services_env):
    services = services_env
    record = services.upsertCheckIn(
        {
            "person_id": "P1",
            "ci_status": "CheckedIn",
            "arrival_time": _iso_now(),
            "location": "ICP",
        }
    )
    assert record.personnel_status.value == "Available"
    roster = services.getRoster({"include_no_show": True})
    assert roster[0].person_id == "P1"
    assert roster[0].personnel_status.value == "Available"


def test_demobilize_sets_status_and_history(services_env, tmp_path):
    services = services_env
    first = services.upsertCheckIn(
        {
            "person_id": "P1",
            "ci_status": "CheckedIn",
            "arrival_time": _iso_now(),
            "location": "ICP",
        }
    )
    second = services.upsertCheckIn(
        {
            "person_id": "P1",
            "ci_status": "Demobilized",
            "arrival_time": first.arrival_time,
            "location": "ICP",
            "expected_updated_at": first.updated_at,
        }
    )
    assert second.personnel_status.value == "Demobilized"
    history = services.getHistory("P1")
    assert any(event.event_type == "DEMOB" for event in history)
    # Repeat demobilize should not create additional DEMOB history
    third = services.upsertCheckIn(
        {
            "person_id": "P1",
            "ci_status": "Demobilized",
            "arrival_time": first.arrival_time,
            "location": "ICP",
            "expected_updated_at": second.updated_at,
        }
    )
    history_after = services.getHistory("P1")
    demob_events = [event for event in history_after if event.event_type == "DEMOB"]
    assert len(demob_events) == 1
    assert third.personnel_status.value == "Demobilized"
    assert third.ui_flags.grayed


def test_no_show_guard_blocks_when_activity_exists(services_env):
    services = services_env
    first = services.upsertCheckIn(
        {
            "person_id": "P2",
            "ci_status": "CheckedIn",
            "arrival_time": _iso_now(),
            "location": "ICP",
            "team_id": "T1",
            "role_on_team": "Lead",
        }
    )
    # Change assignment to create activity history
    second = services.upsertCheckIn(
        {
            "person_id": "P2",
            "ci_status": "CheckedIn",
            "arrival_time": first.arrival_time,
            "location": "ICP",
            "team_id": "T2",
            "role_on_team": "Lead",
            "expected_updated_at": first.updated_at,
        }
    )
    with pytest.raises(checkin_exceptions.NoShowGuardError):
        services.upsertCheckIn(
            {
                "person_id": "P2",
                "ci_status": "NoShow",
                "arrival_time": first.arrival_time,
                "location": "ICP",
                "expected_updated_at": second.updated_at,
            }
        )


def test_pending_does_not_auto_flip_personnel_status(services_env):
    services = services_env
    services.setOffline(False)
    initial = services.upsertCheckIn(
        {
            "person_id": "P1",
            "ci_status": "CheckedIn",
            "arrival_time": _iso_now(),
            "location": "ICP",
            "team_id": "T1",
            "role_on_team": "Medic",
            "override_personnel_status": "Assigned",
            "override_reason": "Manual assignment",
        }
    )
    second = services.upsertCheckIn(
        {
            "person_id": "P1",
            "ci_status": "Pending",
            "arrival_time": initial.arrival_time,
            "location": "ICP",
            "team_id": "T1",
            "role_on_team": "Medic",
            "expected_updated_at": initial.updated_at,
        }
    )
    assert second.personnel_status.value == "Assigned"


def test_override_requires_permission(tmp_path, monkeypatch):
    services, schema = _setup_environment(tmp_path, monkeypatch)
    _seed_personnel(tmp_path, schema)
    app_state.AppState.set_active_user_role("Planning")
    with pytest.raises(checkin_exceptions.PermissionDenied):
        services.upsertCheckIn(
            {
                "person_id": "P1",
                "ci_status": "CheckedIn",
                "arrival_time": _iso_now(),
                "location": "ICP",
                "override_personnel_status": "Assigned",
                "override_reason": "Need assignment",
            }
        )


def test_filters_hide_no_show_by_default(services_env):
    services = services_env
    first = services.upsertCheckIn(
        {
            "person_id": "P1",
            "ci_status": "NoShow",
            "arrival_time": _iso_now(),
            "location": "ICP",
        }
    )
    assert first.personnel_status.value == "Unavailable"
    roster_default = services.getRoster({})
    assert roster_default == []
    roster_with_no_show = services.getRoster({"include_no_show": True})
    assert roster_with_no_show[0].person_id == "P1"
    assert roster_with_no_show[0].ui_flags.hidden_by_default


def test_conflict_detection_raises(services_env):
    services = services_env
    first = services.upsertCheckIn(
        {
            "person_id": "P1",
            "ci_status": "CheckedIn",
            "arrival_time": _iso_now(),
            "location": "ICP",
        }
    )
    # Update once to change updated_at
    services.upsertCheckIn(
        {
            "person_id": "P1",
            "ci_status": "AtICP",
            "arrival_time": first.arrival_time,
            "location": "ICP",
            "expected_updated_at": first.updated_at,
        }
    )
    with pytest.raises(checkin_exceptions.ConflictError):
        services.upsertCheckIn(
            {
                "person_id": "P1",
                "ci_status": "OffDuty",
                "arrival_time": first.arrival_time,
                "location": "ICP",
                "expected_updated_at": first.updated_at,
            }
        )


def test_offline_queue_and_flush(tmp_path, monkeypatch):
    services, schema = _setup_environment(tmp_path, monkeypatch)
    _seed_personnel(tmp_path, schema)
    services.setOffline(True)
    with pytest.raises(checkin_exceptions.OfflineQueued) as exc_info:
        services.upsertCheckIn(
            {
                "person_id": "P1",
                "ci_status": "CheckedIn",
                "arrival_time": _iso_now(),
                "location": "ICP",
            }
        )
    queued_record = exc_info.value.record
    assert queued_record.pending
    assert services.pendingQueueCount() == 1
    services.setOffline(False)
    services.flushOfflineQueue()
    assert services.pendingQueueCount() == 0
    roster = services.getRoster({"include_no_show": True})
    assert roster and roster[0].person_id == "P1"
