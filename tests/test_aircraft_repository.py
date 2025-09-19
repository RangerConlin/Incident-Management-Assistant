from __future__ import annotations

from pathlib import Path

import pytest

from modules.logistics.aircraft.repository import AircraftRepository


@pytest.fixture()
def repo(tmp_path: Path) -> AircraftRepository:
    db_path = tmp_path / "aircraft.db"
    repository = AircraftRepository(db_path=db_path)
    return repository


def _sample_payload() -> dict[str, object]:
    return {
        "tail_number": "TEST123",
        "callsign": "TEST",
        "type": "Helicopter",
        "make_model_display": "Sample Model",
        "base": "TEST",
        "status": "Available",
        "fuel_type": "Jet A",
        "range_nm": 100,
        "endurance_hr": 2.5,
        "crew_min": 2,
        "crew_max": 4,
    }


def test_create_and_fetch_aircraft(repo: AircraftRepository) -> None:
    created = repo.create_aircraft(_sample_payload())
    assert created.id is not None
    fetched = repo.fetch_aircraft(created.id)
    assert fetched is not None
    assert fetched.tail_number == "TEST123"


def test_set_status_clears_assignment(repo: AircraftRepository) -> None:
    payload = _sample_payload() | {
        "assigned_team_name": "Team A",
        "assigned_team_id": "team-a",
    }
    record = repo.create_aircraft(payload)
    repo.set_status([record.id], "Out of Service", "maintenance")
    updated = repo.fetch_aircraft(record.id)
    assert updated is not None
    assert updated.status == "Out of Service"
    assert updated.assigned_team_name is None


def test_import_rows_merge(repo: AircraftRepository) -> None:
    repo.create_aircraft(_sample_payload())
    incoming = [
        {
            "tail_number": "TEST123",
            "callsign": "UPDATED",
            "type": "Helicopter",
            "status": "Assigned",
        }
    ]
    result = repo.import_rows(incoming, update_existing=True, conflict_mode="overwrite")
    assert result["updated"] == 1
    updated = repo.fetch_aircraft(1)
    assert updated is not None
    assert updated.callsign == "UPDATED"
    assert updated.status == "Assigned"


def test_list_filters_apply(repo: AircraftRepository) -> None:
    repo.create_aircraft(_sample_payload())
    repo.create_aircraft(
        _sample_payload()
        | {
            "tail_number": "TEST456",
            "type": "UAS",
            "status": "Assigned",
            "fuel_type": "Electric",
            "cap_nvg": True,
        }
    )
    rows, total = repo.list_aircraft({"type": "UAS"})
    assert total == 1
    assert rows[0].tail_number == "TEST456"

