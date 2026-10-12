from __future__ import annotations

import pytest

from modules.logistics.facilities.repository import ApiFacilitiesRepository
from utils.incident_cache import incident_cache


def _failing_get(*args, **kwargs):
    raise AssertionError("repository should use the active incident cache")


@pytest.fixture(autouse=True)
def _clear_incident_cache():
    incident_cache.clear()
    yield
    incident_cache.clear()


def _repo(monkeypatch) -> ApiFacilitiesRepository:
    repo = ApiFacilitiesRepository("INC-CACHE")
    monkeypatch.setattr("modules.logistics.facilities.repository.api_client.get", _failing_get)
    return repo


def test_list_facilities_reads_from_cache_sorted_and_filtered(monkeypatch):
    repo = _repo(monkeypatch)
    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "facilities": [
                {"_id": "f-2", "name": "Zulu Base", "facility_type": "base", "status": "active"},
                {"_id": "f-1", "name": "Alpha Staging", "facility_type": "staging", "status": "closed"},
                {"_id": "f-3", "name": "Bravo Base", "facility_type": "base", "status": "active"},
            ]
        },
    )

    all_facilities = repo.list_facilities()
    assert [f.name for f in all_facilities] == ["Bravo Base", "Zulu Base", "Alpha Staging"]
    assert [f.id for f in all_facilities] == ["f-3", "f-2", "f-1"]

    active_only = repo.list_facilities(status="active")
    assert [f.name for f in active_only] == ["Bravo Base", "Zulu Base"]

    staging_only = repo.list_facilities(facility_type="staging")
    assert [f.name for f in staging_only] == ["Alpha Staging"]


def test_get_facility_reads_from_cache(monkeypatch):
    repo = _repo(monkeypatch)
    incident_cache.load_snapshot(
        "INC-CACHE",
        {"facilities": [{"_id": "f-1", "name": "ICP", "facility_type": "command_post", "status": "active"}]},
    )

    facility = repo.get_facility("f-1")

    assert facility is not None
    assert facility.name == "ICP"
    assert facility.id == "f-1"


def test_get_facility_missing_from_cache_returns_none_without_api_call(monkeypatch):
    repo = _repo(monkeypatch)
    incident_cache.load_snapshot(
        "INC-CACHE",
        {"facilities": [{"_id": "f-1", "name": "ICP", "facility_type": "command_post", "status": "active"}]},
    )

    assert repo.get_facility("does-not-exist") is None


def test_list_and_get_fall_back_to_api_without_active_cache(monkeypatch):
    """No incident_cache snapshot loaded for this incident -> hits the API."""
    repo = ApiFacilitiesRepository("INC-NO-CACHE")
    calls: list[str] = []

    def fake_get(path, params=None):
        calls.append(path)
        return []

    monkeypatch.setattr("modules.logistics.facilities.repository.api_client.get", fake_get)

    assert repo.list_facilities() == []
    assert calls == ["/api/incidents/INC-NO-CACHE/facilities"]
