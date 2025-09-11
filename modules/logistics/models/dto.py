"""Data transfer objects and enums for Logistics module."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class PersonStatus(str, Enum):
    """Lifecycle status for personnel resources."""

    AVAILABLE = "Available"
    ASSIGNED = "Assigned"
    PENDING = "Pending"
    UNAVAILABLE = "Unavailable"
    DEMOBILIZED = "Demobilized"


class CheckInStatus(str, Enum):
    """Check in state for personnel."""

    CHECKED_IN = "CheckedIn"
    PENDING = "Pending"
    NO_SHOW = "NoShow"
    DEMOBILIZED = "Demobilized"


class ResourceStatus(str, Enum):
    """Status for equipment, vehicles and aircraft."""

    AVAILABLE = "Available"
    ASSIGNED = "Assigned"
    OUT_OF_SERVICE = "OutOfService"


@dataclass(slots=True)
class Personnel:
    """Represents an individual resource participating in an incident."""

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
    """Equipment available for use in an incident."""

    id: Optional[int]
    name: str
    type: str
    serial: str
    assigned_team_id: Optional[int]
    status: ResourceStatus
    notes: str = ""


@dataclass(slots=True)
class Vehicle:
    """Vehicle available for use in an incident."""

    id: Optional[int]
    name: str
    type: str
    callsign: str
    assigned_team_id: Optional[int]
    status: ResourceStatus
    notes: str = ""


@dataclass(slots=True)
class Aircraft:
    """Aircraft tracked for an incident."""

    id: Optional[int]
    tail: str
    type: str
    callsign: str
    assigned_team_id: Optional[int]
    status: ResourceStatus
    notes: str = ""


@dataclass(slots=True)
class CheckInRecord:
    """Historical check in/out events for personnel."""

    id: Optional[int]
    personnel_id: int
    incident_id: str
    checkin_status: CheckInStatus
    when_ts: float
    who: str
    where: str
    notes: str = ""
