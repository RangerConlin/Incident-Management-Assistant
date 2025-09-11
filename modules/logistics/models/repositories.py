"""Data access layer for the Logistics module.

The repository classes provide thin wrappers around ``sqlite3`` queries.  They
operate on the dataclasses defined in :mod:`dto` and intentionally avoid using
any ORM so the code remains lightweight and easy to test.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Iterator, Optional, Sequence

from .dto import (
    Aircraft,
    CheckInRecord,
    Equipment,
    Personnel,
    Vehicle,
    CheckInStatus,
    PersonStatus,
    ResourceStatus,
)


class _RepoBase:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)


class PersonnelRepo(_RepoBase):
    TABLE = "personnel"

    def list(self) -> list[Personnel]:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT id,callsign,first_name,last_name,role,team_id,phone,status,checkin_status,notes FROM personnel"
            )
            rows = cur.fetchall()
        return [self._row_to_personnel(r) for r in rows]

    def create(self, person: Personnel) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO personnel (callsign,first_name,last_name,role,team_id,phone,status,checkin_status,notes) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    person.callsign,
                    person.first_name,
                    person.last_name,
                    person.role,
                    person.team_id,
                    person.phone,
                    person.status.value,
                    person.checkin_status.value,
                    person.notes,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def update(self, person: Personnel) -> None:
        if person.id is None:
            raise ValueError("person.id required for update")
        with self._connect() as conn:
            conn.execute(
                "UPDATE personnel SET callsign=?,first_name=?,last_name=?,role=?,team_id=?,phone=?,status=?,checkin_status=?,notes=?,updated_at=strftime('%s','now') WHERE id=?",
                (
                    person.callsign,
                    person.first_name,
                    person.last_name,
                    person.role,
                    person.team_id,
                    person.phone,
                    person.status.value,
                    person.checkin_status.value,
                    person.notes,
                    person.id,
                ),
            )
            conn.commit()

    def delete(self, person_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM personnel WHERE id=?", (person_id,))
            conn.commit()

    @staticmethod
    def _row_to_personnel(row: Sequence) -> Personnel:
        return Personnel(
            id=row[0],
            callsign=row[1],
            first_name=row[2],
            last_name=row[3],
            role=row[4],
            team_id=row[5],
            phone=row[6],
            status=PersonStatus(row[7]),
            checkin_status=CheckInStatus(row[8]),
            notes=row[9] or "",
        )


class EquipmentRepo(_RepoBase):
    TABLE = "equipment"

    def list(self) -> list[Equipment]:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT id,name,type,serial,assigned_team_id,status,notes FROM equipment"
            )
            return [self._row_to_equipment(r) for r in cur.fetchall()]

    def create(self, eq: Equipment) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO equipment (name,type,serial,assigned_team_id,status,notes) VALUES (?,?,?,?,?,?)",
                (
                    eq.name,
                    eq.type,
                    eq.serial,
                    eq.assigned_team_id,
                    eq.status.value,
                    eq.notes,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def update(self, eq: Equipment) -> None:
        if eq.id is None:
            raise ValueError("equipment.id required for update")
        with self._connect() as conn:
            conn.execute(
                "UPDATE equipment SET name=?,type=?,serial=?,assigned_team_id=?,status=?,notes=?,updated_at=strftime('%s','now') WHERE id=?",
                (
                    eq.name,
                    eq.type,
                    eq.serial,
                    eq.assigned_team_id,
                    eq.status.value,
                    eq.notes,
                    eq.id,
                ),
            )
            conn.commit()

    def delete(self, eq_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM equipment WHERE id=?", (eq_id,))
            conn.commit()

    @staticmethod
    def _row_to_equipment(row: Sequence) -> Equipment:
        return Equipment(
            id=row[0],
            name=row[1],
            type=row[2],
            serial=row[3],
            assigned_team_id=row[4],
            status=ResourceStatus(row[5]),
            notes=row[6] or "",
        )


class VehicleRepo(_RepoBase):
    TABLE = "vehicles"

    def list(self) -> list[Vehicle]:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT id,name,type,callsign,assigned_team_id,status,notes FROM vehicles"
            )
            return [self._row_to_vehicle(r) for r in cur.fetchall()]

    def create(self, v: Vehicle) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO vehicles (name,type,callsign,assigned_team_id,status,notes) VALUES (?,?,?,?,?,?)",
                (
                    v.name,
                    v.type,
                    v.callsign,
                    v.assigned_team_id,
                    v.status.value,
                    v.notes,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def update(self, v: Vehicle) -> None:
        if v.id is None:
            raise ValueError("vehicle.id required for update")
        with self._connect() as conn:
            conn.execute(
                "UPDATE vehicles SET name=?,type=?,callsign=?,assigned_team_id=?,status=?,notes=?,updated_at=strftime('%s','now') WHERE id=?",
                (
                    v.name,
                    v.type,
                    v.callsign,
                    v.assigned_team_id,
                    v.status.value,
                    v.notes,
                    v.id,
                ),
            )
            conn.commit()

    def delete(self, vehicle_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM vehicles WHERE id=?", (vehicle_id,))
            conn.commit()

    @staticmethod
    def _row_to_vehicle(row: Sequence) -> Vehicle:
        return Vehicle(
            id=row[0],
            name=row[1],
            type=row[2],
            callsign=row[3],
            assigned_team_id=row[4],
            status=ResourceStatus(row[5]),
            notes=row[6] or "",
        )


class AircraftRepo(_RepoBase):
    TABLE = "aircraft"

    def list(self) -> list[Aircraft]:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT id,tail,type,callsign,assigned_team_id,status,notes FROM aircraft"
            )
            return [self._row_to_aircraft(r) for r in cur.fetchall()]

    def create(self, a: Aircraft) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO aircraft (tail,type,callsign,assigned_team_id,status,notes) VALUES (?,?,?,?,?,?)",
                (
                    a.tail,
                    a.type,
                    a.callsign,
                    a.assigned_team_id,
                    a.status.value,
                    a.notes,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def update(self, a: Aircraft) -> None:
        if a.id is None:
            raise ValueError("aircraft.id required for update")
        with self._connect() as conn:
            conn.execute(
                "UPDATE aircraft SET tail=?,type=?,callsign=?,assigned_team_id=?,status=?,notes=?,updated_at=strftime('%s','now') WHERE id=?",
                (
                    a.tail,
                    a.type,
                    a.callsign,
                    a.assigned_team_id,
                    a.status.value,
                    a.notes,
                    a.id,
                ),
            )
            conn.commit()

    def delete(self, aircraft_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM aircraft WHERE id=?", (aircraft_id,))
            conn.commit()

    @staticmethod
    def _row_to_aircraft(row: Sequence) -> Aircraft:
        return Aircraft(
            id=row[0],
            tail=row[1],
            type=row[2],
            callsign=row[3],
            assigned_team_id=row[4],
            status=ResourceStatus(row[5]),
            notes=row[6] or "",
        )


class CheckInRepo(_RepoBase):
    TABLE = "checkins"

    def create(self, rec: CheckInRecord) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO checkins (personnel_id,incident_id,checkin_status,when_ts,who,where,notes) VALUES (?,?,?,?,?,?,?)",
                (
                    rec.personnel_id,
                    rec.incident_id,
                    rec.checkin_status.value,
                    rec.when_ts,
                    rec.who,
                    rec.where,
                    rec.notes,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def list_for_personnel(self, person_id: int) -> list[CheckInRecord]:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT id,personnel_id,incident_id,checkin_status,when_ts,who,where,notes FROM checkins WHERE personnel_id=? ORDER BY when_ts DESC",
                (person_id,),
            )
            return [self._row_to_record(r) for r in cur.fetchall()]

    @staticmethod
    def _row_to_record(row: Sequence) -> CheckInRecord:
        return CheckInRecord(
            id=row[0],
            personnel_id=row[1],
            incident_id=row[2],
            checkin_status=CheckInStatus(row[3]),
            when_ts=row[4],
            who=row[5] or "",
            where=row[6] or "",
            notes=row[7] or "",
        )


class AuditRepo(_RepoBase):
    TABLE = "audit_log"

    def log(self, actor: str, action: str, table: str, target_id: int | None, before: dict | None, after: dict | None) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO audit_log (actor,action,target_table,target_id,before_json,after_json) VALUES (?,?,?,?,?,?)",
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
