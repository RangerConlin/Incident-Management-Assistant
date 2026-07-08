from __future__ import annotations

import pytest

from modules.planning.operational_periods.repository import OperationalPeriodRepository
from utils.incident_cache import incident_cache


def _failing_get(*args, **kwargs):
    raise AssertionError("repository should use the active incident cache")


@pytest.fixture(autouse=True)
def _clear_incident_cache():
    incident_cache.clear()
    yield
    incident_cache.clear()


def _repo(monkeypatch) -> OperationalPeriodRepository:
    repo = OperationalPeriodRepository(incident_id="INC-CACHE")
    monkeypatch.setattr("utils.api_client.api_client.get", _failing_get)
    return repo


def test_list_periods_reads_from_cache_sorted_by_number(monkeypatch):
    repo = _repo(monkeypatch)
    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "operational_periods": [
                {"_id": "p-2", "int_id": 2, "incident_id": "INC-CACHE", "number": 2, "name": "Night Ops", "status": "Planned"},
                {"_id": "p-1", "int_id": 1, "incident_id": "INC-CACHE", "number": 1, "name": "Day Ops", "status": "Complete"},
            ]
        },
    )

    periods = repo.list_periods()

    assert [p.name for p in periods] == ["Day Ops", "Night Ops"]
    assert [p.id for p in periods] == [1, 2]


def test_get_period_reads_single_doc_from_cache(monkeypatch):
    repo = _repo(monkeypatch)
    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "operational_periods": [
                {"_id": "p-1", "int_id": 1, "incident_id": "INC-CACHE", "number": 1, "name": "Day Ops"},
            ]
        },
    )

    period = repo.get_period(1)

    assert period.name == "Day Ops"


def test_get_active_period_picks_most_recently_updated_active(monkeypatch):
    repo = _repo(monkeypatch)
    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "operational_periods": [
                {
                    "_id": "p-1", "int_id": 1, "incident_id": "INC-CACHE", "number": 1,
                    "status": "Complete", "updated_at": "2026-07-06T00:00:00+00:00",
                },
                {
                    "_id": "p-2", "int_id": 2, "incident_id": "INC-CACHE", "number": 2,
                    "status": "Active", "updated_at": "2026-07-07T09:00:00+00:00",
                },
                {
                    "_id": "p-3", "int_id": 3, "incident_id": "INC-CACHE", "number": 3,
                    "status": "Active", "updated_at": "2026-07-07T10:00:00+00:00",
                },
            ]
        },
    )

    active = repo.get_active_period()

    assert active is not None
    assert active.id == 3


def test_get_active_period_returns_none_when_nothing_active(monkeypatch):
    repo = _repo(monkeypatch)
    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "operational_periods": [
                {"_id": "p-1", "int_id": 1, "incident_id": "INC-CACHE", "number": 1, "status": "Planned"},
            ]
        },
    )

    assert repo.get_active_period() is None


def test_list_periods_falls_back_to_api_without_active_cache(monkeypatch):
    repo = OperationalPeriodRepository(incident_id="INC-NO-CACHE")
    calls: list[str] = []

    def fake_get(path):
        calls.append(path)
        return []

    monkeypatch.setattr("utils.api_client.api_client.get", fake_get)

    assert repo.list_periods() == []
    assert calls == ["/api/incidents/INC-NO-CACHE/planning/operational-periods"]
