"""Data transfer objects and enums for the Logistics module.

These dataclasses are intentionally lightweight so they can be reused by
widgets, services and tests without pulling in any Qt dependencies.  Only
standard library types are used which keeps the objects easily serialisable.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class PersonStatus(str, Enum):
    """Overall availability status for a person."""

    AVAILABLE = "Available"
    ASSIGNED = "Assigned"
    PENDING = "Pending"
    UNAVAILABLE = "Unavailable"
    DEMOBILIZED = "Demobilized"


class CheckInStatus(str, Enum):
    """Check‑in lifecycle state for personnel."""

    CHECKED_IN = "CheckedIn"
    PENDING = "Pending"
    NO_SHOW = "NoShow"
    DEMOBILIZED = "Demobilized"


class ResourceStatus(str, Enum):
    """Status shared by equipment, vehicles and aircraft."""

    AVAILABLE = "Available"
    ASSIGNED = "Assigned"
    OUT_OF_SERVICE = "OutOfService"


@dataclass(slots=True)
class Personnel:
    """Representation of a person for an incident."""

    id: Optional[int]
    callsign: str
    first_name: str
    last_name: str
    role: str
    team_id: Optional[int]
    phone: str
    status: PersonStatus
    checkin_status: CheckInStatus
    notes: str = ""


@dataclass(slots=True)
class Equipment:
    id: Optional[int]
    name: str
    type: str
    serial: str
    assigned_team_id: Optional[int]
    status: ResourceStatus
    notes: str = ""


@dataclass(slots=True)
class Vehicle:
    id: Optional[int]
    name: str
    type: str
    callsign: str
    assigned_team_id: Optional[int]
    status: ResourceStatus
    notes: str = ""


@dataclass(slots=True)
class Aircraft:
    id: Optional[int]
    tail: str
    type: str
    callsign: str
    assigned_team_id: Optional[int]
    status: ResourceStatus
    notes: str = ""


@dataclass(slots=True)
class CheckInRecord:
    """Audit of individual check‑in/out events."""

    id: Optional[int]
    personnel_id: int
    incident_id: str
    checkin_status: CheckInStatus
    when_ts: float
    who: str
    where: str
    notes: str = ""
