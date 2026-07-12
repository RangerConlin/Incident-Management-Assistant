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


def test_list_positions_reads_from_incident_org_cache(monkeypatch):
    repo = _repo(monkeypatch)
    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "incident_org": [
                {"_id": "p-1", "position_id": 2, "title": "Ops Chief", "sort_order": 1},
                {"_id": "p-2", "position_id": 1, "title": "IC", "sort_order": 0},
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
            "incident_org": [
                {"_id": "p-1", "position_id": 1, "title": "IC", "sort_order": 0},
                {"_id": "p-2", "position_id": 2, "title": "Retired", "sort_order": 1},
            ]
        },
    )

    positions = repo.list_positions(include_inactive=True)

    assert {p.title for p in positions} == {"IC", "Retired"}


def test_list_operational_units_filters_classification(monkeypatch):
    repo = _repo(monkeypatch)
    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "incident_org": [
                {"_id": "p-1", "position_id": 1, "title": "Ops Branch", "classification": "branch"},
                {"_id": "p-2", "position_id": 2, "title": "Safety", "classification": "position"},
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
            "incident_org": [
                {
                    "_id": "p-5",
                    "position_id": 5,
                    "title": "Ops",
                    "primary": [
                        {"person_record": 10, "end_time": None},
                        {"person_record": 11, "end_time": "2026-07-01T00:00:00+00:00"},
                    ],
                },
                {"_id": "p-6", "position_id": 6, "title": "Plans", "primary": [{"person_record": 12, "end_time": None}]},
            ],
            "incident_personnel": [
                {"_id": "ip-10", "person_record": 10, "name": "Alex Current"},
                {"_id": "ip-11", "person_record": 11, "name": "Blake Done"},
            ],
        },
    )

    active_for_position = repo.list_assignments(position_id=5)
    assert [a.id for a in active_for_position] == ["5:primary:10"]
    assert [a.person_name for a in active_for_position] == ["Alex Current"]

    all_for_position = repo.list_assignments(position_id=5, active_only=False)
    assert sorted(a.id for a in all_for_position) == ["5:primary:10", "5:primary:11"]


def test_list_assignments_for_person(monkeypatch):
    repo = _repo(monkeypatch)
    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "incident_org": [
                {"_id": "p-5", "position_id": 5, "title": "Ops", "primary": [{"person_record": 10, "end_time": None}]},
                {
                    "_id": "p-6",
                    "position_id": 6,
                    "title": "Plans",
                    "deputies": [{"person_record": 10, "end_time": "2026-07-01T00:00:00+00:00"}],
                },
            ]
        },
    )

    active = repo.list_assignments_for_person(10)
    assert [a.id for a in active] == ["5:primary:10"]

    everything = repo.list_assignments_for_person(10, active_only=False)
    assert sorted(a.id for a in everything) == ["5:primary:10", "6:deputies:10"]


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
