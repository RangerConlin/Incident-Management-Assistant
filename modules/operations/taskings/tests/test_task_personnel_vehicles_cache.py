from __future__ import annotations

import pytest

from modules.operations.taskings import repository
from utils.incident_cache import incident_cache


class _FailingClient:
    def get(self, *args, **kwargs):
        raise AssertionError("list_task_personnel should read from the active incident cache")


@pytest.fixture(autouse=True)
def _clear_incident_cache():
    incident_cache.clear()
    yield
    incident_cache.clear()


def test_list_task_personnel_reads_from_incident_cache(monkeypatch):
    monkeypatch.setattr(repository.incident_context, "get_active_incident_id", lambda: "INC-CACHE")
    monkeypatch.setattr(repository, "_client", lambda: _FailingClient())

    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "tasks": [
                {
                    "_id": "task-doc-1",
                    "int_id": 3,
                    "task_teams": [{"team_id": 7}],
                }
            ],
            "teams": [
                {
                    "_id": "team-doc-1",
                    "int_id": 7,
                    "name": "Ground 7",
                    "members_json": "[42, 43]",
                }
            ],
            "incident_personnel": [
                {"_id": "pers-1", "person_record": 42, "name": "Alex Morgan", "rank": "GTM3", "phone": "555-0100"},
                {"_id": "pers-2", "master_id": 43, "first_name": "Jamie", "last_name": "Lee"},
            ],
        },
    )

    rows = repository.list_task_personnel(3)

    by_id = {r["id"]: r for r in rows}
    assert by_id[42]["name"] == "Alex Morgan"
    assert by_id[42]["rank"] == "GTM3"
    assert by_id[42]["phone"] == "555-0100"
    assert by_id[43]["name"] == "Jamie Lee"


def test_list_task_personnel_falls_back_to_api_without_active_cache(monkeypatch):
    monkeypatch.setattr(repository.incident_context, "get_active_incident_id", lambda: "INC-NO-CACHE")
    calls: list[str] = []

    class _FakeClient:
        def get(self, path, *args, **kwargs):
            calls.append(path)
            return [{"id": 1, "name": "Fallback Person"}]

    monkeypatch.setattr(repository, "_client", lambda: _FakeClient())

    rows = repository.list_task_personnel(9)

    assert rows == [{"id": 1, "name": "Fallback Person"}]
    assert calls == ["/api/incidents/INC-NO-CACHE/operations/tasks/9/personnel"]
