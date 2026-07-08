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
            "checkin_history": [
                {"_id": "h-1", "person_record": 5, "ts": "2026-07-07T09:00:00+00:00", "actor": "A", "event_type": "NOTE", "payload": {}},
                {"_id": "h-2", "person_record": 5, "ts": "2026-07-07T10:00:00+00:00", "actor": "B", "event_type": "ASSIGNMENT_CHANGE", "payload": {}},
                {"_id": "h-3", "person_record": 9, "ts": "2026-07-07T11:00:00+00:00", "actor": "C", "event_type": "NOTE", "payload": {}},
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
            "checkin_history": [
                {"_id": "h-1", "person_record": 5, "ts": "2026-07-07T09:00:00+00:00", "actor": "A", "event_type": "NOTE", "payload": {}},
            ]
        },
        meta={"truncated": {"checkin_history": {"loaded": 1, "total": 900, "reason": "collection document limit"}}},
    )

    calls: list[str] = []

    class _FakeClient:
        def get(self, path):
            calls.append(path)
            return [{"ts": "2026-01-01T00:00:00+00:00", "actor": "Z", "event_type": "OLD", "payload": {}}]

    monkeypatch.setattr(repository, "_client", lambda: _FakeClient())

    items = repository.list_history(5)

    assert calls == ["/api/incidents/INC-TRUNCATED/checkin/history/5"]
    assert [i.event_type for i in items] == ["OLD"]


class _FailingClient:
    def get(self, *args, **kwargs):
        raise AssertionError("list_history should use the active incident cache")
