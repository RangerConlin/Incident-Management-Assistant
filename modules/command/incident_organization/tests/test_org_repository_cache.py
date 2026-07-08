from __future__ import annotations

import pytest

from modules.command.incident_organization.repository import ApiIncidentOrganizationRepository
from utils.incident_cache import incident_cache


def _failing_get(*args, **kwargs):
    raise AssertionError("repository should use the active incident cache")


@pytest.fixture(autouse=True)
def _clear_incident_cache():
    incident_cache.clear()
    yield
    incident_cache.clear()


def _repo(monkeypatch) -> ApiIncidentOrganizationRepository:
    repo = ApiIncidentOrganizationRepository("INC-CACHE")
    monkeypatch.setattr("utils.api_client.api_client.get", _failing_get)
    return repo


def test_list_positions_reads_from_cache_and_filters_inactive(monkeypatch):
    repo = _repo(monkeypatch)
    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "org_positions": [
                {"_id": "p-1", "position_id": 2, "title": "Ops Chief", "status": "active", "sort_order": 1},
                {"_id": "p-2", "position_id": 1, "title": "IC", "status": "active", "sort_order": 0},
                {"_id": "p-3", "position_id": 3, "title": "Retired", "status": "inactive", "sort_order": 2},
            ]
        },
    )

    positions = repo.list_positions()

    assert [p.title for p in positions] == ["IC", "Ops Chief"]


def test_list_positions_include_inactive(monkeypatch):
    repo = _repo(monkeypatch)
    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "org_positions": [
                {"_id": "p-1", "position_id": 1, "title": "IC", "status": "active", "sort_order": 0},
                {"_id": "p-2", "position_id": 2, "title": "Retired", "status": "inactive", "sort_order": 1},
            ]
        },
    )

    positions = repo.list_positions(include_inactive=True)

    assert {p.title for p in positions} == {"IC", "Retired"}


def test_list_operational_units_filters_classification_and_status(monkeypatch):
    repo = _repo(monkeypatch)
    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "org_positions": [
                {"_id": "p-1", "position_id": 1, "title": "Ops Branch", "status": "active", "classification": "branch"},
                {"_id": "p-2", "position_id": 2, "title": "Safety", "status": "active", "classification": "position"},
                {"_id": "p-3", "position_id": 3, "title": "Old Branch", "status": "inactive", "classification": "branch"},
            ]
        },
    )

    units = repo.list_operational_units()

    assert [u.title for u in units] == ["Ops Branch"]


def test_list_assignments_filters_active_and_position(monkeypatch):
    repo = _repo(monkeypatch)
    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "org_assignments": [
                {"_id": "a-1", "assignment_id": 1, "position_id": 5, "person_record": 10, "end_time": None},
                {"_id": "a-2", "assignment_id": 2, "position_id": 5, "person_record": 11, "end_time": "2026-07-01T00:00:00+00:00"},
                {"_id": "a-3", "assignment_id": 3, "position_id": 6, "person_record": 12, "end_time": None},
            ]
        },
    )

    active_for_position = repo.list_assignments(position_id=5)
    assert [a.id for a in active_for_position] == [1]

    all_for_position = repo.list_assignments(position_id=5, active_only=False)
    assert sorted(a.id for a in all_for_position) == [1, 2]


def test_list_assignments_for_person(monkeypatch):
    repo = _repo(monkeypatch)
    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "org_assignments": [
                {"_id": "a-1", "assignment_id": 1, "position_id": 5, "person_record": 10, "end_time": None},
                {"_id": "a-2", "assignment_id": 2, "position_id": 6, "person_record": 10, "end_time": "2026-07-01T00:00:00+00:00"},
            ]
        },
    )

    active = repo.list_assignments_for_person(10)
    assert [a.id for a in active] == [1]

    everything = repo.list_assignments_for_person(10, active_only=False)
    assert sorted(a.id for a in everything) == [1, 2]


def test_list_assignment_history_reads_from_cache(monkeypatch):
    repo = _repo(monkeypatch)
    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "org_history": [
                {"_id": "h-2", "history_id": 2, "position_id": 5, "created_at": "2026-07-07T01:00:00+00:00", "action": "assigned"},
                {"_id": "h-1", "history_id": 1, "position_id": 5, "created_at": "2026-07-07T00:00:00+00:00", "action": "created"},
            ]
        },
    )

    history = repo.list_assignment_history(position_id=5)

    assert [h.id for h in history] == [1, 2]


def test_list_positions_falls_back_to_api_without_active_cache(monkeypatch):
    """No incident_cache snapshot loaded for this incident -> hits the API."""
    repo = ApiIncidentOrganizationRepository("INC-NO-CACHE")
    calls: list[tuple[str, dict]] = []

    def fake_get(path, params=None):
        calls.append((path, params or {}))
        return []

    monkeypatch.setattr("utils.api_client.api_client.get", fake_get)

    assert repo.list_positions() == []
    assert calls == [("/api/incidents/INC-NO-CACHE/org/positions", {"include_inactive": "false"})]
