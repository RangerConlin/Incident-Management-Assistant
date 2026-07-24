from __future__ import annotations

import pytest

from modules.safety import services
from utils.incident_cache import incident_cache


def _failing_get(*args, **kwargs):
    raise AssertionError("service should use the active incident cache")


@pytest.fixture(autouse=True)
def _clear_incident_cache(monkeypatch):
    incident_cache.clear()
    monkeypatch.setattr(services.api_client, "get", _failing_get)
    yield
    incident_cache.clear()


def test_list_safety_reports_filters_from_cache():
    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "safety_reports": [
                {
                    "_id": "s-2", "id": 2, "incident_id": "INC-CACHE",
                    "time": "2026-07-07T10:00:00+00:00", "severity": "High",
                    "flagged": True, "notes": "Slip hazard near ICP",
                },
                {
                    "_id": "s-1", "id": 1, "incident_id": "INC-CACHE",
                    "time": "2026-07-07T09:00:00+00:00", "severity": "Low",
                    "flagged": False, "notes": "Minor scrape",
                },
            ]
        },
    )

    reports = services.list_safety_reports("INC-CACHE")
    assert [r.id for r in reports] == [1, 2]

    flagged = services.list_safety_reports("INC-CACHE", flagged=True)
    assert [r.id for r in flagged] == [2]

    searched = services.list_safety_reports("INC-CACHE", q="slip")
    assert [r.id for r in searched] == [2]

    by_severity = services.list_safety_reports("INC-CACHE", severity="Low")
    assert [r.id for r in by_severity] == [1]


def test_list_medical_incidents_reads_from_cache():
    incident_cache.load_snapshot(
        "INC-CACHE",
        {"medical_incidents": [{"_id": "m-1", "id": 1, "incident_id": "INC-CACHE", "type": "sprain"}]},
    )

    incidents = services.list_medical_incidents("INC-CACHE")
    assert [i.id for i in incidents] == [1]
    assert incidents[0].type == "sprain"


def test_list_triage_entries_reads_from_cache():
    incident_cache.load_snapshot(
        "INC-CACHE",
        {"triage_entries": [{"_id": "t-1", "id": 1, "incident_id": "INC-CACHE", "patient_tag": "P-1"}]},
    )

    entries = services.list_triage_entries("INC-CACHE")
    assert [e.id for e in entries] == [1]


def test_list_hazard_zones_reads_from_cache():
    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "spatial_features": [
                {
                    "_id": "h-1",
                    "int_id": 1,
                    "incident_id": "INC-CACHE",
                    "feature_type": "hazard_zone",
                    "label": "Cliff Edge",
                    "geometry_wkt": "POINT(-83.1 42.1)",
                    "status": "active",
                },
                {
                    "_id": "p-1",
                    "int_id": 2,
                    "incident_id": "INC-CACHE",
                    "feature_type": "planning_sketch",
                    "label": "Not a hazard",
                },
            ]
        },
    )

    zones = services.list_hazard_zones("INC-CACHE")
    assert [z.id for z in zones] == [1]
    assert zones[0].name == "Cliff Edge"
    assert zones[0].geometry_wkt == "POINT(-83.1 42.1)"


def test_list_and_get_iwi_reports_from_cache():
    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "iwi_reports": [
                {"_id": "iwi-2", "id": 2, "incident_id": "INC-CACHE", "actual_severity": "Minor", "status": "draft"},
                {"_id": "iwi-1", "id": 1, "incident_id": "INC-CACHE", "actual_severity": "Serious", "status": "closed"},
            ]
        },
    )

    all_reports = services.list_iwi_reports("INC-CACHE")
    assert [r["id"] for r in all_reports] == [1, 2]

    closed_only = services.list_iwi_reports("INC-CACHE", status="closed")
    assert [r["id"] for r in closed_only] == [1]

    report = services.get_iwi_report("INC-CACHE", "iwi-2")
    assert report is not None
    assert report["id"] == 2


def test_get_iwi_report_missing_from_cache_falls_back_to_api(monkeypatch):
    incident_cache.load_snapshot(
        "INC-CACHE",
        {"iwi_reports": [{"_id": "iwi-1", "id": 1, "incident_id": "INC-CACHE"}]},
    )
    calls: list[str] = []

    def fake_get(path):
        calls.append(path)
        return {"id": 99}

    monkeypatch.setattr(services.api_client, "get", fake_get)

    result = services.get_iwi_report("INC-CACHE", "does-not-exist")

    assert result == {"id": 99}
    assert calls == ["/api/incidents/INC-CACHE/safety/iwi/does-not-exist"]


def test_list_safety_reports_falls_back_to_api_without_active_cache(monkeypatch):
    calls: list[str] = []

    def fake_get(path, params=None):
        calls.append(path)
        return []

    monkeypatch.setattr(services.api_client, "get", fake_get)

    assert services.list_safety_reports("INC-NO-CACHE") == []
    assert calls == ["/api/incidents/INC-NO-CACHE/safety/reports"]
