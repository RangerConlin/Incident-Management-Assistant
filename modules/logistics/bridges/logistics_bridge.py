"""Public bridge for interacting with the logistics service.

Other modules import this bridge rather than talking to the repositories
or services directly.  The bridge keeps a single ``LogisticsService`` instance
for the active incident which can be swapped when the user selects a new
incident.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..models.dto import (
    Aircraft,
    Equipment,
    Personnel,
    Vehicle,
    CheckInStatus,
)
from ..models.services import LogisticsService

_active_service: LogisticsService | None = None


def set_active_incident(incident_id: str, base_path: Path | str = Path("data/incidents")) -> None:
    global _active_service
    _active_service = LogisticsService(incident_id, base_path)


def get_active_incident() -> Optional[str]:
    return _active_service.incident_id if _active_service else None


# Personnel -------------------------------------------------------------

def list_personnel() -> list[Personnel]:
    _require_service()
    return _active_service.list_personnel()


def create_or_update_personnel(actor: str, person: Personnel) -> int:
    _require_service()
    if person.id is None:
        return _active_service.create_personnel(actor, person)
    _active_service.update_personnel(actor, person)
    return person.id


def delete_personnel(actor: str, person_id: int) -> None:
    _require_service()
    _active_service.delete_personnel(actor, person_id)


def record_checkin(actor: str, personnel_id: int, status: CheckInStatus, location: str = "", notes: str = "") -> int:
    _require_service()
    return _active_service.record_checkin(actor, personnel_id, status, location, notes)


# Equipment -------------------------------------------------------------

def list_equipment() -> list[Equipment]:
    _require_service()
    return _active_service.equipment.list()


def save_equipment(actor: str, eq: Equipment) -> int:
    _require_service()
    return _active_service.save_equipment(actor, eq)


def delete_equipment(actor: str, eq_id: int) -> None:
    _require_service()
    _active_service.delete_equipment(actor, eq_id)


# Vehicles --------------------------------------------------------------

def list_vehicles() -> list[Vehicle]:
    _require_service()
    return _active_service.vehicles.list()


def save_vehicle(actor: str, v: Vehicle) -> int:
    _require_service()
    return _active_service.save_vehicle(actor, v)


def delete_vehicle(actor: str, v_id: int) -> None:
    _require_service()
    _active_service.delete_vehicle(actor, v_id)


# Aircraft --------------------------------------------------------------

def list_aircraft() -> list[Aircraft]:
    _require_service()
    return _active_service.aircraft.list()


def save_aircraft(actor: str, a: Aircraft) -> int:
    _require_service()
    return _active_service.save_aircraft(actor, a)


def delete_aircraft(actor: str, a_id: int) -> None:
    _require_service()
    _active_service.delete_aircraft(actor, a_id)


def _require_service() -> None:
    if _active_service is None:
        raise RuntimeError("Active incident not set; call set_active_incident() first")
