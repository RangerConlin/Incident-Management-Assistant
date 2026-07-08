from __future__ import annotations

import pytest

from modules.operations.taskings import repository
from utils.catalog_cache import catalog_cache
from utils.incident_cache import incident_cache


class _FailingClient:
    def get(self, *args, **kwargs):
        raise AssertionError("repository should use the active incident cache")


@pytest.fixture(autouse=True)
def _clear_incident_cache():
    incident_cache.clear()
    catalog_cache.invalidate()
    yield
    incident_cache.clear()
    catalog_cache.invalidate()


def test_task_detail_reads_task_and_teams_from_incident_cache(monkeypatch):
    monkeypatch.setattr(repository.incident_context, "get_active_incident_id", lambda: "INC-CACHE")
    monkeypatch.setattr(repository, "_client", lambda: _FailingClient())

    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "tasks": [
                {
                    "_id": "task-doc-1",
                    "int_id": 7,
                    "task_id": "T-007",
                    "title": "Search east ridge",
                    "priority": "High",
                    "status": "Assigned",
                    "task_teams": [
                        {
                            "id": 11,
                            "team_id": 3,
                            "team_name": "Ground 3",
                            "team_leader": "A. Lead",
                            "team_leader_phone": "555-0100",
                            "is_primary": True,
                            "time_assigned": "2026-07-07T12:00:00+00:00",
                        }
                    ],
                }
            ]
        },
    )

    detail = repository.get_task_detail(7)

    assert detail.task.task_id == "T-007"
    assert detail.task.title == "Search east ridge"
    assert len(detail.teams) == 1
    assert detail.teams[0].team_name == "Ground 3"
    assert detail.teams[0].primary is True


def test_assignment_and_logs_read_from_incident_cache(monkeypatch):
    monkeypatch.setattr(repository.incident_context, "get_active_incident_id", lambda: "INC-CACHE")
    monkeypatch.setattr(repository, "_client", lambda: _FailingClient())

    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "tasks": [
                {
                    "_id": "task-doc-2",
                    "int_id": 8,
                    "task_assignment": {"ground": {"time_allocated": "2 hr"}},
                    "audit": [
                        {
                            "ts_utc": "2026-07-07T12:00:00+00:00",
                            "field_changed": "Status",
                            "old_value": "Draft",
                            "new_value": "Assigned",
                        }
                    ],
                    "task_teams": [
                        {
                            "id": 12,
                            "team_id": 4,
                            "team_name": "Ground 4",
                            "time_enroute": "2026-07-07T12:10:00+00:00",
                        }
                    ],
                }
            ]
        },
    )

    assert repository.get_task_assignment(8)["ground"]["time_allocated"] == "2 hr"
    assert repository.list_audit_logs(8, search="assigned")[0]["field_changed"] == "Status"
    assert repository.list_team_status_log(8)[0]["time_enroute"] == "2026-07-07T12:10:00+00:00"


def test_list_objectives_reads_and_normalizes_from_incident_cache(monkeypatch):
    monkeypatch.setattr(repository.incident_context, "get_active_incident_id", lambda: "INC-CACHE")
    monkeypatch.setattr(repository, "_client", lambda: _FailingClient())

    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "incident_objectives": [
                {
                    "_id": "obj-2", "display_order": 2, "created_at": "2026-07-07T00:00:00+00:00",
                    "text": "Locate subject",
                },
                {
                    "_id": "obj-1", "display_order": 1, "created_at": "2026-07-06T00:00:00+00:00",
                    "description": "Establish perimeter", "objective_id": "OBJ-1",
                },
            ]
        },
    )

    objectives = repository.list_objectives()

    assert [o["text"] for o in objectives] == ["Establish perimeter", "Locate subject"]
    assert objectives[0]["code"] == "OBJ-1"
    assert objectives[0]["task_links"] == []


def test_list_objectives_falls_back_to_api_without_active_cache(monkeypatch):
    monkeypatch.setattr(repository.incident_context, "get_active_incident_id", lambda: "INC-NO-CACHE")
    calls: list[tuple[str, dict]] = []

    class _FakeClient:
        def get(self, path, params=None):
            calls.append((path, params or {}))
            return []

    monkeypatch.setattr(repository, "_client", lambda: _FakeClient())

    assert repository.list_objectives() == []
    assert calls == [("/api/objectives", {"incident_id": "INC-NO-CACHE"})]


def test_list_and_get_task_debriefs_from_incident_cache(monkeypatch):
    monkeypatch.setattr(repository.incident_context, "get_active_incident_id", lambda: "INC-CACHE")
    monkeypatch.setattr(repository, "_client", lambda: _FailingClient())

    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "task_debriefs": [
                {
                    "_id": "d-1", "int_id": 1, "task_id": 7,
                    "sortie_number": "S-1", "archived": False,
                },
                {
                    "_id": "d-2", "int_id": 2, "task_id": 7,
                    "sortie_number": "S-2", "archived": True,
                },
                {
                    "_id": "d-3", "int_id": 3, "task_id": 8,
                    "sortie_number": "S-3", "archived": False,
                },
            ]
        },
    )

    debriefs = repository.list_task_debriefs(7)
    assert [d["int_id"] for d in debriefs] == [1]

    archived = repository.get_debrief(2)
    assert archived["sortie_number"] == "S-2"


def test_get_debrief_missing_from_cache_falls_back_to_api(monkeypatch):
    monkeypatch.setattr(repository.incident_context, "get_active_incident_id", lambda: "INC-CACHE")

    incident_cache.load_snapshot(
        "INC-CACHE",
        {"task_debriefs": [{"_id": "d-1", "int_id": 1, "task_id": 7, "sortie_number": "S-1"}]},
    )

    calls: list[str] = []

    class _FakeClient:
        def get(self, path):
            calls.append(path)
            return {"int_id": 999, "sortie_number": "from-api"}

    monkeypatch.setattr(repository, "_client", lambda: _FakeClient())

    result = repository.get_debrief(999)

    assert result == {"int_id": 999, "sortie_number": "from-api"}
    assert calls == ["/api/incidents/INC-CACHE/operations/debriefs/999"]


def test_list_task_debriefs_falls_back_to_api_without_active_cache(monkeypatch):
    monkeypatch.setattr(repository.incident_context, "get_active_incident_id", lambda: "INC-NO-CACHE")
    calls: list[str] = []

    class _FakeClient:
        def get(self, path):
            calls.append(path)
            return []

    monkeypatch.setattr(repository, "_client", lambda: _FakeClient())

    assert repository.list_task_debriefs(7) == []
    assert calls == ["/api/incidents/INC-NO-CACHE/operations/tasks/7/debriefs"]


def test_list_incident_channels_and_task_comms_from_cache(monkeypatch):
    from utils.api_client import api_client

    monkeypatch.setattr(repository.incident_context, "get_active_incident_id", lambda: "INC-CACHE")
    monkeypatch.setattr(repository, "_client", lambda: _FailingClient())
    monkeypatch.setattr(
        api_client, "get",
        lambda path, params=None: [
            {"id": 5, "name": "Command 1", "function": "Command", "rx_freq": 155.0}
        ],
    )

    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "incident_channels": [
                {"_id": "c-1", "channel_id": "INC-CACHE-CH-1", "master_id": "5", "sort_index": 1},
            ],
            "tasks": [
                {
                    "_id": "task-doc-9", "int_id": 9,
                    "comms": [
                        {"id": 1, "incident_channel_id": 1, "function": "", "remarks": "test"},
                    ],
                }
            ],
        },
    )

    channels = repository.list_incident_channels()
    assert channels[0]["channel"] == "Command 1"

    comms = repository.list_task_comms(9)
    assert comms[0]["channel_name"] == "Command 1"
    assert comms[0]["rx_frequency"] == 155.0
    assert comms[0]["remarks"] == "test"


def test_list_incident_channels_falls_back_to_api_without_active_cache(monkeypatch):
    monkeypatch.setattr(repository.incident_context, "get_active_incident_id", lambda: "INC-NO-CACHE")
    calls: list[str] = []

    class _FakeClient:
        def get(self, path):
            calls.append(path)
            return []

    monkeypatch.setattr(repository, "_client", lambda: _FakeClient())

    assert repository.list_incident_channels() == []
    assert calls == ["/api/incidents/INC-NO-CACHE/channels-plan"]
