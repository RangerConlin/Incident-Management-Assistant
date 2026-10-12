"""Input validation helpers for the check-in module."""
from __future__ import annotations

from typing import Dict, List


REQUIRED_PERSONNEL_FIELDS = ["id", "first_name", "last_name"]
REQUIRED_EQUIPMENT_FIELDS = ["id", "name"]
REQUIRED_VEHICLE_FIELDS = ["id", "name"]
REQUIRED_AIRCRAFT_FIELDS = ["id", "tail_number"]


def _validate(payload: Dict[str, str], required: List[str]) -> List[str]:
    """Return a list of error messages for missing required fields."""
    errors = []
    for field in required:
        if not payload.get(field):
            errors.append(f"{field} is required")
    return errors


def validate_personnel(payload: Dict[str, str]) -> List[str]:
    return _validate(payload, REQUIRED_PERSONNEL_FIELDS)


def validate_equipment(payload: Dict[str, str]) -> List[str]:
    return _validate(payload, REQUIRED_EQUIPMENT_FIELDS)


def validate_vehicle(payload: Dict[str, str]) -> List[str]:
    return _validate(payload, REQUIRED_VEHICLE_FIELDS)


def validate_aircraft(payload: Dict[str, str]) -> List[str]:
    return _validate(payload, REQUIRED_AIRCRAFT_FIELDS)
