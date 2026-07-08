from __future__ import annotations

import pytest

from modules.operations.teams.data import repository
from utils.incident_cache import incident_cache


class _FailingClient:
    def get(self, *args, **kwargs):
        raise AssertionError("repository should use the active incident cache")


@pytest.fixture(autouse=True)
def _clear_incident_cache():
    incident_cache.clear()
    yield
    incident_cache.clear()


def test_get_team_reads_from_incident_cache(monkeypatch):
    monkeypatch.setattr(repository, "_active_incident_id", lambda: "INC-CACHE")
    monkeypatch.setattr(repository, "_client", lambda: _FailingClient())

    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "teams": [
                {
                    "_id": "team-doc-1",
                    "int_id": 3,
                    "name": "Ground 3",
                    "callsign": "GT-3",
                    "team_leader": 42,
                    "status": "available",
                    "members_json": "[42, 43]",
                }
            ]
        },
    )

    team = repository.get_team(3)

    assert team is not None
    assert team.name == "Ground 3"
    assert team.team_leader_id == 42
    assert team.members == [42, 43]


def test_get_team_falls_back_to_leader_personnel_phone(monkeypatch):
    monkeypatch.setattr(repository, "_active_incident_id", lambda: "INC-CACHE")
    monkeypatch.setattr(repository, "_client", lambda: _FailingClient())

    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "teams": [
                {
                    "_id": "team-doc-2",
                    "int_id": 4,
                    "name": "Ground 4",
                    "team_leader": 55,
                }
            ],
            "incident_personnel": [
                {"_id": "pers-1", "person_record": 55, "phone": "555-0199"},
            ],
        },
    )

    team = repository.get_team(4)

    assert team is not None
    assert team.team_leader_phone == "555-0199"


def test_list_all_teams_reads_from_incident_cache(monkeypatch):
    from modules.operations.taskings import repository as task_repo

    monkeypatch.setattr(task_repo.incident_context, "get_active_incident_id", lambda: "INC-CACHE")
    monkeypatch.setattr(task_repo, "_client", lambda: _FailingClient())

    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "teams": [
                {"_id": "team-doc-3", "int_id": 2, "name": "Ground 2"},
                {"_id": "team-doc-4", "int_id": 1, "name": "Ground 1"},
            ]
        },
    )

    teams = task_repo.list_all_teams()

    assert [t["team_id"] for t in teams] == [1, 2]
    assert teams[0]["team_name"] == "Ground 1"


def test_get_checked_in_teams_reads_from_incident_cache(monkeypatch):
    monkeypatch.setattr(repository, "_active_incident_id", lambda: "INC-CACHE")
    monkeypatch.setattr(repository, "_client", lambda: _FailingClient())

    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "teams": [
                {"_id": "t-1", "int_id": 1, "name": "Zulu", "status": "Available", "disbanded": False},
                {"_id": "t-2", "int_id": 2, "name": "Alpha", "status": "Assigned", "disbanded": False},
                {"_id": "t-3", "int_id": 3, "name": "Bravo", "status": "Available", "disbanded": True},
                {"_id": "t-4", "int_id": 4, "name": "Charlie", "status": "Planned", "disbanded": False},
            ]
        },
    )

    checked_in = repository.get_checked_in_teams()
    assert [t["name"] for t in checked_in] == ["Alpha", "Zulu"]
    assert all(t["checked_in"] for t in checked_in)

    unchecked = repository.get_unchecked_teams()
    assert [t["name"] for t in unchecked] == ["Charlie"]
    assert all(not t["checked_in"] for t in unchecked)


def test_get_checked_in_teams_falls_back_to_api_without_active_cache(monkeypatch):
    monkeypatch.setattr(repository, "_active_incident_id", lambda: None)
    calls: list[tuple[str, dict]] = []

    class _FakeClient:
        def get(self, path, params=None):
            calls.append((path, params or {}))
            return []

    monkeypatch.setattr(repository, "_client", lambda: _FakeClient())
    monkeypatch.setattr("utils.incident_context.get_active_incident_id", lambda: "INC-NO-CACHE")

    assert repository.get_checked_in_teams() == []
    assert calls == [
        (
            "/api/incidents/INC-NO-CACHE/checkin/teams/checked-state",
            {"checked_in": True, "include_disbanded": False},
        )
    ]
