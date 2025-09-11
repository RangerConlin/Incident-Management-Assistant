"""Bridge exposing logistics functionality to the rest of the app."""
from __future__ import annotations

from typing import Optional

from ..models.dto import Aircraft, CheckInStatus, Equipment, Personnel, Vehicle
from ..models.services import LogisticsService
from ..reports import ics211_report, ics218_report

_active_incident_id: Optional[str] = None
_service: Optional[LogisticsService] = None


def set_active_incident(incident_id: str, actor: str = "system") -> None:
    """Initialize repositories for the given incident."""
    global _active_incident_id, _service
    _active_incident_id = incident_id
    _service = LogisticsService(incident_id, actor)


def get_active_incident() -> Optional[str]:
    return _active_incident_id


def _svc() -> LogisticsService:
    if _service is None:
        raise RuntimeError("LogisticsService not initialised. Call set_active_incident().")
    return _service


# Personnel --------------------------------------------------------------

def list_personnel() -> list[Personnel]:
    return _svc().list_personnel()


def create_or_update_personnel(person: Personnel) -> int:
    return _svc().save_personnel(person)


def delete_personnel(person_id: int) -> None:
    _svc().delete_personnel(person_id)


def record_checkin(personnel_id: int, status: CheckInStatus, meta: dict) -> int:
    return _svc().record_checkin(personnel_id, status, meta)


# Equipment --------------------------------------------------------------

def list_equipment() -> list[Equipment]:
    return _svc().equipment_repo.list()


def create_or_update_equipment(eq: Equipment) -> int:
    return _svc().save_equipment(eq)


def delete_equipment(equipment_id: int) -> None:
    _svc().delete_equipment(equipment_id)


# Vehicles ---------------------------------------------------------------

def list_vehicles() -> list[Vehicle]:
    return _svc().vehicle_repo.list()


def create_or_update_vehicle(v: Vehicle) -> int:
    return _svc().save_vehicle(v)


def delete_vehicle(vehicle_id: int) -> None:
    _svc().delete_vehicle(vehicle_id)


# Aircraft ---------------------------------------------------------------

def list_aircraft() -> list[Aircraft]:
    return _svc().aircraft_repo.list()


def create_or_update_aircraft(a: Aircraft) -> int:
    return _svc().save_aircraft(a)


def delete_aircraft(aircraft_id: int) -> None:
    _svc().delete_aircraft(aircraft_id)


# Reports ---------------------------------------------------------------

def print_ics211() -> None:
    """Generate and show ICS211 report."""
    ics211_report.print_report(_svc())


def print_ics218() -> None:
    ics218_report.print_report(_svc())
