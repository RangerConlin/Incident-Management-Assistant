from __future__ import annotations

import sqlite3

from modules.planning.operational_periods.repository import OperationalPeriodRepository


def test_repository_migrates_legacy_operationalperiods_table(tmp_path) -> None:
    db_path = tmp_path / "incident.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE operationalperiods (
            id INTEGER PRIMARY KEY,
            mission_id TEXT,
            op_number TEXT,
            start_time TEXT,
            end_time TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO operationalperiods (mission_id, op_number, start_time, end_time)
        VALUES ('INC-1', 'OP7', '2026-06-11T07:00:00', '2026-06-11T19:00:00')
        """
    )
    conn.commit()
    conn.close()

    repo = OperationalPeriodRepository(incident_id="INC-1", db_path=db_path)
    period = repo.list_periods()[0]

    assert period.number == 7
    assert period.incident_id == "INC-1"

    conn = sqlite3.connect(db_path)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(operationalperiods)").fetchall()}
    conn.close()
    assert {"incident_id", "number", "status", "objectives", "updated_at"}.issubset(columns)


def test_repository_creates_and_sets_active_period(tmp_path) -> None:
    repo = OperationalPeriodRepository(incident_id="INC-2", db_path=tmp_path / "incident.db")
    created = repo.create_period(
        {
            "number": 1,
            "start_time": "2026-06-11T07:00:00",
            "end_time": "2026-06-11T19:00:00",
            "name": "Day Shift",
        }
    )

    active = repo.set_active_period(created.id or 0)

    assert active.id == created.id
    assert active.status == "Active"
    assert repo.get_active_period() is not None
    assert repo.get_active_period().id == created.id


def test_repository_rejects_overlapping_periods(tmp_path) -> None:
    repo = OperationalPeriodRepository(incident_id="INC-3", db_path=tmp_path / "incident.db")
    repo.create_period(
        {
            "number": 1,
            "start_time": "2026-06-11T07:00:00",
            "end_time": "2026-06-11T19:00:00",
        }
    )

    try:
        repo.create_period(
            {
                "number": 2,
                "start_time": "2026-06-11T18:00:00",
                "end_time": "2026-06-12T06:00:00",
            }
        )
    except ValueError as exc:
        assert "overlaps" in str(exc)
    else:
        raise AssertionError("Expected overlap validation to fail")
