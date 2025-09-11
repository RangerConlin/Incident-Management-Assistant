"""Business logic for the Logistics module."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from .dto import (
    Aircraft,
    CheckInRecord,
    CheckInStatus,
    Equipment,
    PersonStatus,
    Personnel,
    ResourceStatus,
    Vehicle,
)
from .repositories import (
    AircraftRepo,
    AuditRepo,
    CheckInRepo,
    EquipmentRepo,
    PersonnelRepo,
    VehicleRepo,
)
from ..data.schemas import ensure_incident_schema


class LogisticsService:
    """High level operations over the logistics repositories."""

    def __init__(self, incident_id: str, base_path: Path | str = Path("data/incidents")):
        self.incident_id = incident_id
        self.db_path = Path(base_path) / f"{incident_id}.db"
        ensure_incident_schema(self.db_path)
        # repositories
        self.personnel = PersonnelRepo(self.db_path)
        self.equipment = EquipmentRepo(self.db_path)
        self.vehicles = VehicleRepo(self.db_path)
        self.aircraft = AircraftRepo(self.db_path)
        self.checkins = CheckInRepo(self.db_path)
        self.audit = AuditRepo(self.db_path)

    # Personnel ---------------------------------------------------------

    def list_personnel(self) -> list[Personnel]:
        return self.personnel.list()

    def create_personnel(self, actor: str, person: Personnel) -> int:
        pid = self.personnel.create(person)
        self.audit.log(actor, "create", PersonnelRepo.TABLE, pid, None, person.__dict__)
        return pid

    def update_personnel(self, actor: str, person: Personnel) -> None:
        before = None
        if person.id is not None:
            for p in self.personnel.list():
                if p.id == person.id:
                    before = p.__dict__
                    break
        self.personnel.update(person)
        self.audit.log(actor, "update", PersonnelRepo.TABLE, person.id, before, person.__dict__)

    def delete_personnel(self, actor: str, person_id: int) -> None:
        self.personnel.delete(person_id)
        self.audit.log(actor, "delete", PersonnelRepo.TABLE, person_id, None, None)

    # Check-in ----------------------------------------------------------

    def record_checkin(
        self,
        actor: str,
        personnel_id: int,
        status: CheckInStatus,
        location: str = "",
        notes: str = "",
    ) -> int:
        """Record a check-in/out and update personnel status."""

        now = time.time()
        rec = CheckInRecord(
            id=None,
            personnel_id=personnel_id,
            incident_id=self.incident_id,
            checkin_status=status,
            when_ts=now,
            who=actor,
            where=location,
            notes=notes,
        )
        rid = self.checkins.create(rec)

        # apply auto status rules
        person_list = self.personnel.list()
        person = next((p for p in person_list if p.id == personnel_id), None)
        if not person:
            return rid

        if status is CheckInStatus.PENDING:
            person.status = PersonStatus.PENDING
        elif status is CheckInStatus.NO_SHOW:
            person.status = PersonStatus.UNAVAILABLE
        elif status is CheckInStatus.DEMOBILIZED:
            person.status = PersonStatus.DEMOBILIZED
        elif status is CheckInStatus.CHECKED_IN and person.team_id is None:
            person.status = PersonStatus.AVAILABLE
        person.checkin_status = status
        self.personnel.update(person)
        self.audit.log(actor, "checkin", CheckInRepo.TABLE, rid, None, rec.__dict__)
        return rid

    # Equipment / Vehicles / Aircraft ----------------------------------

    def _save_resource(self, actor: str, repo, table: str, obj, before: dict | None = None) -> int | None:
        if obj.id is None:
            rid = repo.create(obj)
            self.audit.log(actor, "create", table, rid, None, obj.__dict__)
            return rid
        else:
            repo.update(obj)
            self.audit.log(actor, "update", table, obj.id, before, obj.__dict__)
            return obj.id

    def save_equipment(self, actor: str, eq: Equipment) -> int:
        if eq.status is ResourceStatus.OUT_OF_SERVICE:
            eq.assigned_team_id = None
        before = None
        if eq.id:
            before = next((e.__dict__ for e in self.equipment.list() if e.id == eq.id), None)
        return int(self._save_resource(actor, self.equipment, EquipmentRepo.TABLE, eq, before))

    def save_vehicle(self, actor: str, v: Vehicle) -> int:
        if v.status is ResourceStatus.OUT_OF_SERVICE:
            v.assigned_team_id = None
        before = None
        if v.id:
            before = next((e.__dict__ for e in self.vehicles.list() if e.id == v.id), None)
        return int(self._save_resource(actor, self.vehicles, VehicleRepo.TABLE, v, before))

    def save_aircraft(self, actor: str, a: Aircraft) -> int:
        if a.status is ResourceStatus.OUT_OF_SERVICE:
            a.assigned_team_id = None
        before = None
        if a.id:
            before = next((e.__dict__ for e in self.aircraft.list() if e.id == a.id), None)
        return int(self._save_resource(actor, self.aircraft, AircraftRepo.TABLE, a, before))

    def delete_equipment(self, actor: str, eq_id: int) -> None:
        self.equipment.delete(eq_id)
        self.audit.log(actor, "delete", EquipmentRepo.TABLE, eq_id, None, None)

    def delete_vehicle(self, actor: str, v_id: int) -> None:
        self.vehicles.delete(v_id)
        self.audit.log(actor, "delete", VehicleRepo.TABLE, v_id, None, None)

    def delete_aircraft(self, actor: str, a_id: int) -> None:
        self.aircraft.delete(a_id)
        self.audit.log(actor, "delete", AircraftRepo.TABLE, a_id, None, None)
