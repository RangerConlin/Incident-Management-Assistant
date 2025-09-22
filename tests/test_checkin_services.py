from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Dict

import pytest

from modules.logistics.checkin import services
from utils import incident_context
from utils import db as db_module


@pytest.fixture(autouse=True)
def _reset_service() -> None:
    services.reset_service()
    yield
    services.reset_service()


@pytest.fixture
def temp_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setenv("CHECKIN_DATA_DIR", str(data_dir))
    db_module._DATA_DIR = data_dir
    incident_context._DATA_DIR = data_dir
    incident_context.set_active_incident("UNITTEST-001")
    return data_dir


def _incident_row(data_dir: Path, table: str, identifier: int | str) -> Dict:
    incident_path = data_dir / "incidents" / "UNITTEST-001.db"
    conn = sqlite3.connect(incident_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            f"SELECT * FROM {table} WHERE id = ?", (identifier,),
        ).fetchone()
        return dict(row) if row is not None else {}
    finally:
        conn.close()


def _record_by_id(records: list[Dict], identifier: int | str) -> Dict:
    for record in records:
        if str(record["id"]) == str(identifier):
            return record
    raise AssertionError(f"Record {identifier!r} not found")


def test_create_and_check_in_personnel(temp_data_dir: Path) -> None:
    service = services.CheckInService()
    created = service.create_master_record(
        "personnel",
        {"name": "Alice Example", "role": "Medic", "callsign": "ECHO1"},
    )
    assert created["name"] == "Alice Example"
    assert not created["_checked_in"]

    identifier = str(created["id"])
    checked = service.check_in("personnel", identifier)
    assert checked["_checked_in"]

    master_rows = service.list_master_records("personnel")
    assert _record_by_id(master_rows, identifier)["_checked_in"]
    incident_row = _incident_row(temp_data_dir, "personnel", int(identifier))
    assert incident_row["name"] == "Alice Example"
    assert incident_row["callsign"] == "ECHO1"


def test_vehicle_requires_identifier(temp_data_dir: Path) -> None:
    service = services.CheckInService()
    with pytest.raises(ValueError):
        service.create_master_record("vehicle", {"make": "Ford"})

    created = service.create_master_record(
        "vehicle",
        {"id": "TRK-42", "make": "Ford", "model": "F150"},
    )
    assert created["id"] == "TRK-42"
    assert created["make"] == "Ford"

    checked = service.check_in("vehicle", "TRK-42")
    assert checked["_checked_in"] is True
    incident_row = _incident_row(temp_data_dir, "vehicles", "TRK-42")
    assert incident_row["model"] == "F150"


def test_missing_record_raises(temp_data_dir: Path) -> None:
    service = services.CheckInService()
    with pytest.raises(ValueError):
        service.check_in("equipment", 999)
