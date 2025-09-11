"""SQLite repositories for logistics module.

These repositories are intentionally light weight. They use the standard
:mod:`sqlite3` module with prepared statements and are easily mocked in tests.
"""
from __future__ import annotations

from dataclasses import asdict
import json
import sqlite3
from pathlib import Path
from typing import Iterable, Optional

from .dto import (
    Aircraft,
    CheckInRecord,
    CheckInStatus,
    Equipment,
    Personnel,
    ResourceStatus,
    Vehicle,
)
from ..data import schemas


DATA_DIR = Path("data")
INCIDENTS_DIR = DATA_DIR / "incidents"


class BaseRepo:
    """Base repository offering connection helpers."""

    def __init__(self, incident_id: str):
        self.incident_id = incident_id
        self.db_path = INCIDENTS_DIR / f"{incident_id}.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            for ddl in schemas.INCIDENT_SCHEMAS:
                cur.execute(ddl)
            conn.commit()


class PersonnelRepository(BaseRepo):
    """CRUD operations for :class:`Personnel`."""

    def list(self) -> list[Personnel]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, callsign, first_name, last_name, role, team_id, phone, status, checkin_status, notes FROM personnel"
            ).fetchall()
            return [
                Personnel(
                    id=row["id"],
                    callsign=row["callsign"],
                    first_name=row["first_name"],
                    last_name=row["last_name"],
                    role=row["role"],
                    team_id=row["team_id"],
                    phone=row["phone"],
                    status=row["status"],
                    checkin_status=row["checkin_status"],
                    notes=row["notes"],
                )
                for row in rows
            ]

    def upsert(self, person: Personnel) -> int:
        data = asdict(person)
        with self._connect() as conn:
            cur = conn.cursor()
            if person.id is None:
                cur.execute(
                    """
                    INSERT INTO personnel (callsign, first_name, last_name, role, team_id, phone, status, checkin_status, notes, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, strftime('%s','now'))
                    """,
                    (
                        data["callsign"],
                        data["first_name"],
                        data["last_name"],
                        data["role"],
                        data["team_id"],
                        data["phone"],
                        data["status"],
                        data["checkin_status"],
                        data["notes"],
                    ),
                )
                person_id = cur.lastrowid
            else:
                cur.execute(
                    """
                    UPDATE personnel SET callsign=?, first_name=?, last_name=?, role=?, team_id=?, phone=?, status=?, checkin_status=?, notes=?, updated_at=strftime('%s','now')
                    WHERE id=?
                    """,
                    (
                        data["callsign"],
                        data["first_name"],
                        data["last_name"],
                        data["role"],
                        data["team_id"],
                        data["phone"],
                        data["status"],
                        data["checkin_status"],
                        data["notes"],
                        data["id"],
                    ),
                )
                person_id = person.id
            conn.commit()
            return int(person_id)

    def delete(self, person_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM personnel WHERE id=?", (person_id,))
            conn.commit()


class EquipmentRepository(BaseRepo):
    def list(self) -> list[Equipment]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, name, type, serial, assigned_team_id, status, notes FROM equipment"
            ).fetchall()
            return [Equipment(**dict(row)) for row in rows]

    def upsert(self, equipment: Equipment) -> int:
        data = asdict(equipment)
        with self._connect() as conn:
            cur = conn.cursor()
            if equipment.id is None:
                cur.execute(
                    """
                    INSERT INTO equipment (name, type, serial, assigned_team_id, status, notes, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, strftime('%s','now'))
                    """,
                    (
                        data["name"],
                        data["type"],
                        data["serial"],
                        data["assigned_team_id"],
                        data["status"],
                        data["notes"],
                    ),
                )
                eid = cur.lastrowid
            else:
                cur.execute(
                    """
                    UPDATE equipment SET name=?, type=?, serial=?, assigned_team_id=?, status=?, notes=?, updated_at=strftime('%s','now')
                    WHERE id=?
                    """,
                    (
                        data["name"],
                        data["type"],
                        data["serial"],
                        data["assigned_team_id"],
                        data["status"],
                        data["notes"],
                        data["id"],
                    ),
                )
                eid = equipment.id
            conn.commit()
            return int(eid)

    def delete(self, equipment_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM equipment WHERE id=?", (equipment_id,))
            conn.commit()


class VehicleRepository(BaseRepo):
    def list(self) -> list[Vehicle]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, name, type, callsign, assigned_team_id, status, notes FROM vehicles"
            ).fetchall()
            return [Vehicle(**dict(row)) for row in rows]

    def upsert(self, vehicle: Vehicle) -> int:
        data = asdict(vehicle)
        with self._connect() as conn:
            cur = conn.cursor()
            if vehicle.id is None:
                cur.execute(
                    """
                    INSERT INTO vehicles (name, type, callsign, assigned_team_id, status, notes, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, strftime('%s','now'))
                    """,
                    (
                        data["name"],
                        data["type"],
                        data["callsign"],
                        data["assigned_team_id"],
                        data["status"],
                        data["notes"],
                    ),
                )
                vid = cur.lastrowid
            else:
                cur.execute(
                    """
                    UPDATE vehicles SET name=?, type=?, callsign=?, assigned_team_id=?, status=?, notes=?, updated_at=strftime('%s','now')
                    WHERE id=?
                    """,
                    (
                        data["name"],
                        data["type"],
                        data["callsign"],
                        data["assigned_team_id"],
                        data["status"],
                        data["notes"],
                        data["id"],
                    ),
                )
                vid = vehicle.id
            conn.commit()
            return int(vid)

    def delete(self, vehicle_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM vehicles WHERE id=?", (vehicle_id,))
            conn.commit()


class AircraftRepository(BaseRepo):
    def list(self) -> list[Aircraft]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, tail, type, callsign, assigned_team_id, status, notes FROM aircraft"
            ).fetchall()
            return [Aircraft(**dict(row)) for row in rows]

    def upsert(self, aircraft: Aircraft) -> int:
        data = asdict(aircraft)
        with self._connect() as conn:
            cur = conn.cursor()
            if aircraft.id is None:
                cur.execute(
                    """
                    INSERT INTO aircraft (tail, type, callsign, assigned_team_id, status, notes, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, strftime('%s','now'))
                    """,
                    (
                        data["tail"],
                        data["type"],
                        data["callsign"],
                        data["assigned_team_id"],
                        data["status"],
                        data["notes"],
                    ),
                )
                aid = cur.lastrowid
            else:
                cur.execute(
                    """
                    UPDATE aircraft SET tail=?, type=?, callsign=?, assigned_team_id=?, status=?, notes=?, updated_at=strftime('%s','now')
                    WHERE id=?
                    """,
                    (
                        data["tail"],
                        data["type"],
                        data["callsign"],
                        data["assigned_team_id"],
                        data["status"],
                        data["notes"],
                        data["id"],
                    ),
                )
                aid = aircraft.id
            conn.commit()
            return int(aid)

    def delete(self, aircraft_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM aircraft WHERE id=?", (aircraft_id,))
            conn.commit()


class CheckInRepository(BaseRepo):
    def record(self, record: CheckInRecord) -> int:
        data = asdict(record)
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO checkins (personnel_id, incident_id, checkin_status, when_ts, who, where, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["personnel_id"],
                    data["incident_id"],
                    data["checkin_status"],
                    data["when_ts"],
                    data["who"],
                    data["where"],
                    data["notes"],
                ),
            )
            cid = cur.lastrowid
            conn.commit()
            return int(cid)


class AuditRepository(BaseRepo):
    def log(self, actor: str, action: str, table: str, target_id: int, before: dict | None, after: dict | None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO audit_log (actor, action, target_table, target_id, before_json, after_json, ts)
                VALUES (?, ?, ?, ?, ?, ?, strftime('%s','now'))
                """,
                (
                    actor,
                    action,
                    table,
                    target_id,
                    json.dumps(before) if before else None,
                    json.dumps(after) if after else None,
                ),
            )
            conn.commit()
