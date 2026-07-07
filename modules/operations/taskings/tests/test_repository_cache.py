from __future__ import annotations

import pytest

from modules.operations.taskings import repository
from utils.incident_cache import incident_cache


class _FailingClient:
    def get(self, *args, **kwargs):
        raise AssertionError("repository should use the active incident cache")


@pytest.fixture(autouse=True)
def _clear_incident_cache():
    incident_cache.clear()
    yield
    incident_cache.clear()


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
