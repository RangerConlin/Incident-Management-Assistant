from __future__ import annotations

import pytest

from modules.statusboards.resource_status_desk import ResourceStatusDesk
from utils import incident_context
from utils.api_client import api_client
from utils.incident_cache import incident_cache


def _failing_get(*args, **kwargs):
    raise AssertionError("resource status desk should use the active incident cache")


@pytest.fixture(autouse=True)
def _clear_incident_cache():
    incident_cache.clear()
    yield
    incident_cache.clear()


def test_fetch_resource_status_docs_reads_from_cache_sorted(monkeypatch):
    monkeypatch.setattr(incident_context, "get_active_incident_id", lambda: "INC-CACHE")
    monkeypatch.setattr(api_client, "get", _failing_get)

    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "resource_status": [
                {"_id": "rs-2", "resource_name": "Zulu Team", "status": "Available"},
                {"_id": "rs-1", "resource_name": "Alpha Team", "status": "Assigned"},
            ]
        },
    )

    docs = ResourceStatusDesk._fetch_resource_status_docs()

    assert [d["resource_name"] for d in docs] == ["Alpha Team", "Zulu Team"]


def test_fetch_team_docs_reads_from_cache(monkeypatch):
    monkeypatch.setattr(incident_context, "get_active_incident_id", lambda: "INC-CACHE")
    monkeypatch.setattr(api_client, "get", _failing_get)

    incident_cache.load_snapshot(
        "INC-CACHE",
        {"teams": [{"_id": "team-1", "int_id": 1, "name": "Ground 1"}]},
    )

    docs = ResourceStatusDesk._fetch_team_docs()

    assert docs[0]["name"] == "Ground 1"


def test_fetch_org_assignments_docs_filters_ended_assignments(monkeypatch):
    monkeypatch.setattr(incident_context, "get_active_incident_id", lambda: "INC-CACHE")
    monkeypatch.setattr(api_client, "get", _failing_get)

    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "org_assignments": [
                {"_id": "a-1", "person_record": 1, "position_id": 10, "end_time": None},
                {"_id": "a-2", "person_record": 2, "position_id": 11, "end_time": "2026-07-01T00:00:00+00:00"},
            ]
        },
    )

    docs = ResourceStatusDesk._fetch_org_assignments_docs()

    assert [d["_id"] for d in docs] == ["a-1"]


def test_fetch_org_positions_docs_filters_inactive(monkeypatch):
    monkeypatch.setattr(incident_context, "get_active_incident_id", lambda: "INC-CACHE")
    monkeypatch.setattr(api_client, "get", _failing_get)

    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "org_positions": [
                {"_id": "p-1", "position_id": 10, "title": "Ops Chief", "status": "active"},
                {"_id": "p-2", "position_id": 11, "title": "Retired Slot", "status": "inactive"},
            ]
        },
    )

    docs = ResourceStatusDesk._fetch_org_positions_docs()

    assert [d["position_id"] for d in docs] == [10]


def test_fetch_helpers_fall_back_to_api_without_active_cache(monkeypatch):
    """No incident_cache snapshot loaded -> methods should still hit the API."""
    monkeypatch.setattr(incident_context, "get_active_incident_id", lambda: "INC-NO-CACHE")
    calls: list[str] = []

    def fake_get(path: str):
        calls.append(path)
        return []

    monkeypatch.setattr(api_client, "get", fake_get)

    assert ResourceStatusDesk._fetch_resource_status_docs() == []
    assert ResourceStatusDesk._fetch_team_docs() == []
    assert ResourceStatusDesk._fetch_org_assignments_docs() == []
    assert ResourceStatusDesk._fetch_org_positions_docs() == []
    assert calls == [
        "/api/incidents/INC-NO-CACHE/resource-status",
        "/api/incidents/INC-NO-CACHE/operations/teams",
        "/api/incidents/INC-NO-CACHE/org/assignments",
        "/api/incidents/INC-NO-CACHE/org/positions",
    ]
