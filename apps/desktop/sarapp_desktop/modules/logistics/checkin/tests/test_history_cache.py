from __future__ import annotations

import pytest

from modules.logistics.checkin import repository
from utils import incident_context
from utils.incident_cache import incident_cache


def _failing_get(*args, **kwargs):
    raise AssertionError("list_history should use the active incident cache")


@pytest.fixture(autouse=True)
def _clear_incident_cache():
    incident_cache.clear()
    yield
    incident_cache.clear()


def test_list_history_reads_from_complete_cache(monkeypatch):
    monkeypatch.setattr(incident_context, "get_active_incident_id", lambda: "INC-CACHE")
    monkeypatch.setattr(repository, "_client", lambda: _FailingClient())

    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "resource_status": [
                {
                    "_id": "rs-5",
                    "entity_type": "personnel",
                    "record_id": 5,
                    "status_log": [
                        {"timestamp": "2026-07-07T09:00:00+00:00", "changed_by": "A", "event_type": "NOTE", "payload": {}},
                        {"timestamp": "2026-07-07T10:00:00+00:00", "changed_by": "B", "event_type": "ASSIGNMENT_CHANGE", "payload": {}},
                    ],
                },
                {"_id": "rs-9", "entity_type": "personnel", "record_id": 9, "status_log": []},
            ]
        },
    )

    items = repository.list_history(5)

    assert [i.event_type for i in items] == ["ASSIGNMENT_CHANGE", "NOTE"]
    assert repository.has_activity(5) is True
    assert repository.has_activity(999) is False


def test_list_history_falls_back_to_api_when_collection_is_truncated(monkeypatch):
    monkeypatch.setattr(incident_context, "get_active_incident_id", lambda: "INC-TRUNCATED")

    incident_cache.load_snapshot(
        "INC-TRUNCATED",
        {
            "resource_status": [
                {"_id": "rs-5", "entity_type": "personnel", "record_id": 5, "status_log": []},
            ]
        },
        meta={"truncated": {"resource_status": {"loaded": 1, "total": 900, "reason": "collection document limit"}}},
    )

    calls: list[str] = []

    class _FakeClient:
        def get(self, path, params=None):
            calls.append((path, params))
            return {
                "entity_type": "personnel",
                "record_id": 5,
                "status_log": [
                    {"timestamp": "2026-01-01T00:00:00+00:00", "changed_by": "Z", "event_type": "OLD", "payload": {}}
                ],
            }

    monkeypatch.setattr(repository, "_client", lambda: _FakeClient())

    items = repository.list_history(5)

    assert calls == [
        (
            "/api/incidents/INC-TRUNCATED/resource-status/by-entity",
            {"entity_type": "personnel", "record_id": "5"},
        )
    ]
    assert [i.event_type for i in items] == ["OLD"]


class _FailingClient:
    def get(self, *args, **kwargs):
        raise AssertionError("list_history should use the active incident cache")
