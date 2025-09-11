"""Business logic for logistics module."""
from __future__ import annotations

import time
from typing import Optional

from .dto import (
    CheckInRecord,
    CheckInStatus,
    Equipment,
    Personnel,
    PersonStatus,
    ResourceStatus,
    Vehicle,
    Aircraft,
)
from .repositories import (
    AuditRepository,
    CheckInRepository,
    EquipmentRepository,
    PersonnelRepository,
    VehicleRepository,
    AircraftRepository,
)


class LogisticsService:
    """High level operations coordinating repositories and rules."""

    def __init__(self, incident_id: str, actor: str = "system") -> None:
        self.incident_id = incident_id
        self.actor = actor
        self.personnel_repo = PersonnelRepository(incident_id)
        self.equipment_repo = EquipmentRepository(incident_id)
        self.vehicle_repo = VehicleRepository(incident_id)
        self.aircraft_repo = AircraftRepository(incident_id)
        self.checkin_repo = CheckInRepository(incident_id)
        self.audit_repo = AuditRepository(incident_id)

    # ------------------------------------------------------------------
    # Personnel
    def list_personnel(self) -> list[Personnel]:
        return self.personnel_repo.list()

    def save_personnel(self, person: Personnel) -> int:
        """Create or update a personnel record with audit logging."""
        before = None
        if person.id:
            before_list = [p for p in self.list_personnel() if p.id == person.id]
            before = before_list[0].__dict__ if before_list else None
        pid = self.personnel_repo.upsert(person)
        self.audit_repo.log(self.actor, "upsert", "personnel", pid, before, person.__dict__)
        return pid

    def delete_personnel(self, person_id: int) -> None:
        before_list = [p for p in self.list_personnel() if p.id == person_id]
        before = before_list[0].__dict__ if before_list else None
        self.personnel_repo.delete(person_id)
        self.audit_repo.log(self.actor, "delete", "personnel", person_id, before, None)

    def record_checkin(self, personnel_id: int, status: CheckInStatus, meta: dict) -> int:
        """Record a check-in/out event and update auto status."""
        person_list = [p for p in self.list_personnel() if p.id == personnel_id]
        if not person_list:
            raise ValueError("personnel not found")
        person = person_list[0]
        before = person.__dict__.copy()
        # Apply auto-status rules
        if status == CheckInStatus.PENDING:
            person.status = PersonStatus.PENDING
        elif status == CheckInStatus.NO_SHOW:
            person.status = PersonStatus.UNAVAILABLE
        elif status == CheckInStatus.DEMOBILIZED:
            person.status = PersonStatus.DEMOBILIZED
        elif status == CheckInStatus.CHECKED_IN and person.status != PersonStatus.ASSIGNED:
            person.status = PersonStatus.AVAILABLE
        person.checkin_status = status
        self.personnel_repo.upsert(person)
        self.audit_repo.log(self.actor, "checkin", "personnel", person.id or 0, before, person.__dict__)
        rec = CheckInRecord(
            id=None,
            personnel_id=personnel_id,
            incident_id=self.incident_id,
            checkin_status=status,
            when_ts=time.time(),
            who=meta.get("who", self.actor),
            where=meta.get("where", ""),
            notes=meta.get("notes", ""),
        )
        return self.checkin_repo.record(rec)

    # ------------------------------------------------------------------
    # Equipment, Vehicles, Aircraft
    def _handle_resource_assignment(self, assigned_team_id: Optional[int], status: ResourceStatus) -> ResourceStatus:
        if status == ResourceStatus.OUT_OF_SERVICE:
            return ResourceStatus.OUT_OF_SERVICE
        if assigned_team_id:
            return ResourceStatus.ASSIGNED
        return ResourceStatus.AVAILABLE

    def save_equipment(self, equipment: Equipment) -> int:
        before = None
        if equipment.id:
            before_list = [e for e in self.equipment_repo.list() if e.id == equipment.id]
            before = before_list[0].__dict__ if before_list else None
        equipment.status = self._handle_resource_assignment(equipment.assigned_team_id, equipment.status)
        if equipment.status == ResourceStatus.OUT_OF_SERVICE:
            equipment.assigned_team_id = None
        eid = self.equipment_repo.upsert(equipment)
        self.audit_repo.log(self.actor, "upsert", "equipment", eid, before, equipment.__dict__)
        return eid

    def delete_equipment(self, equipment_id: int) -> None:
        before_list = [e for e in self.equipment_repo.list() if e.id == equipment_id]
        before = before_list[0].__dict__ if before_list else None
        self.equipment_repo.delete(equipment_id)
        self.audit_repo.log(self.actor, "delete", "equipment", equipment_id, before, None)

    def save_vehicle(self, vehicle: Vehicle) -> int:
        before = None
        if vehicle.id:
            before_list = [v for v in self.vehicle_repo.list() if v.id == vehicle.id]
            before = before_list[0].__dict__ if before_list else None
        vehicle.status = self._handle_resource_assignment(vehicle.assigned_team_id, vehicle.status)
        if vehicle.status == ResourceStatus.OUT_OF_SERVICE:
            vehicle.assigned_team_id = None
        vid = self.vehicle_repo.upsert(vehicle)
        self.audit_repo.log(self.actor, "upsert", "vehicles", vid, before, vehicle.__dict__)
        return vid

    def delete_vehicle(self, vehicle_id: int) -> None:
        before_list = [v for v in self.vehicle_repo.list() if v.id == vehicle_id]
        before = before_list[0].__dict__ if before_list else None
        self.vehicle_repo.delete(vehicle_id)
        self.audit_repo.log(self.actor, "delete", "vehicles", vehicle_id, before, None)

    def save_aircraft(self, aircraft: Aircraft) -> int:
        before = None
        if aircraft.id:
            before_list = [a for a in self.aircraft_repo.list() if a.id == aircraft.id]
            before = before_list[0].__dict__ if before_list else None
        aircraft.status = self._handle_resource_assignment(aircraft.assigned_team_id, aircraft.status)
        if aircraft.status == ResourceStatus.OUT_OF_SERVICE:
            aircraft.assigned_team_id = None
        aid = self.aircraft_repo.upsert(aircraft)
        self.audit_repo.log(self.actor, "upsert", "aircraft", aid, before, aircraft.__dict__)
        return aid

    def delete_aircraft(self, aircraft_id: int) -> None:
        before_list = [a for a in self.aircraft_repo.list() if a.id == aircraft_id]
        before = before_list[0].__dict__ if before_list else None
        self.aircraft_repo.delete(aircraft_id)
        self.audit_repo.log(self.actor, "delete", "aircraft", aircraft_id, before, None)
