from __future__ import annotations

from pathlib import Path

import pytest

from modules.logistics.aircraft.repository import AircraftRepository


@pytest.fixture()
def repo(tmp_path: Path) -> AircraftRepository:
    db_path = tmp_path / "master.db"
    return AircraftRepository(db_path=db_path)


def test_repository_initializes_without_seed_data(repo: AircraftRepository) -> None:
    assert repo.list_aircraft() == []


def test_create_and_status_coupling(repo: AircraftRepository) -> None:
    payload = {
        "tail_number": "N123TEST",
        "callsign": "TEST",
        "type": "Helicopter",
        "make": "Test",
        "model": "Demo",
        "status": "Available",
        "assigned_team_name": "Alpha",
    }
    record = repo.create_aircraft(payload)
    repo.assign_team([record["id"]], "1", "Alpha", notify=False)
    repo.set_status([record["id"]], "Out of Service", notes="maintenance")
    updated = repo.fetch_aircraft(record["id"])
    assert updated is not None
    assert updated["status"] == "Out of Service"
    assert updated["assigned_team_name"] is None


def test_assign_team_updates_fields(repo: AircraftRepository) -> None:
    record = repo.create_aircraft(
        {
            "tail_number": "N456TEST",
            "callsign": "DEMO",
            "type": "UAS",
        }
    )
    repo.assign_team([record["id"]], "42", "Team 42", notify=True)
    updated = repo.fetch_aircraft(record["id"])
    assert updated is not None
    assert updated["assigned_team_name"] == "Team 42"
    assert updated["assigned_team_id"] == "42"

