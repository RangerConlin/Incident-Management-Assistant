"""Exercise the :mod:`services.hospital_service` CRUD helpers."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from models.hospital import Hospital
from services.hospital_service import HospitalService


_COLUMN_DEFS = {
    "code": "code TEXT",
    "type": "type TEXT",
    "phone_er": "phone_er TEXT",
    "phone_switchboard": "phone_switchboard TEXT",
    "fax": "fax TEXT",
    "email": "email TEXT",
    "contact_name": "contact_name TEXT",
    "travel_time_min": "travel_time_min INTEGER",
    "helipad": "helipad INTEGER",
    "trauma_level": "trauma_level TEXT",
    "burn_center": "burn_center INTEGER",
    "pediatric_capability": "pediatric_capability INTEGER",
    "bed_available": "bed_available INTEGER",
    "diversion_status": "diversion_status TEXT",
    "ambulance_radio_channel": "ambulance_radio_channel TEXT",
    "lat": "lat REAL",
    "lon": "lon REAL",
    "is_active": "is_active INTEGER",
}


def _prepare_database(tmp_path: Path) -> Path:
    """Copy the real master DB and ensure expected columns exist for tests."""

    db_copy = tmp_path / "master.db"
    shutil.copy(Path("data/master.db"), db_copy)

    with sqlite3.connect(db_copy) as con:
        existing = {row[1] for row in con.execute("PRAGMA table_info(hospitals)")}
        for column, ddl in _COLUMN_DEFS.items():
            if column not in existing:
                con.execute(f"ALTER TABLE hospitals ADD COLUMN {ddl}")
        con.commit()

    return db_copy


def test_hospital_service_crud(tmp_path: Path) -> None:
    db_path = _prepare_database(tmp_path)
    service = HospitalService(db_path)

    initial_count = len(service.list_hospitals())

    created = Hospital(
        name="Metro Medical Center",
        code="MMC",
        type="Regional",
        address="123 Main Street",
        city="Metropolis",
        state="WA",
        zip="98101",
        contact="Operations Desk",
        contact_name="Dr. Jane Smith",
        phone="555-0100",
        phone_er="555-0101",
        phone_switchboard="555-0102",
        fax="555-0103",
        email="info@metro.org",
        travel_time_min=18,
        helipad=True,
        trauma_level="II",
        burn_center=True,
        pediatric_capability=False,
        bed_available=5,
        diversion_status="Open",
        ambulance_radio_channel="EMS-1",
        notes="Test record",
        lat=47.60,
        lon=-122.33,
        is_active=True,
    )

    new_id = service.create_hospital(created)
    assert new_id > 0

    fetched = service.get_hospital_by_id(new_id)
    assert fetched is not None
    assert fetched.name == "Metro Medical Center"
    assert fetched.helipad is True
    assert fetched.bed_available == 5

    fetched.notes = "Updated notes"
    fetched.helipad = False
    service.update_hospital(fetched)

    updated = service.get_hospital_by_id(new_id)
    assert updated is not None
    assert updated.notes == "Updated notes"
    assert updated.helipad is False

    filtered = service.list_hospitals("metro")
    assert any(row.id == new_id for row in filtered)

    with pytest.raises(ValueError):
        service.create_hospital(Hospital(name="Metro Medical Center"))

    service.delete_hospitals([new_id])
    assert service.get_hospital_by_id(new_id) is None
    assert len(service.list_hospitals()) == initial_count
