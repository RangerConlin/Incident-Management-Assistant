from __future__ import annotations

"""Dataclasses describing the ICS-203 organization structure."""

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class OrgUnit:
    """A node in the incident's organization tree."""

    id: Optional[int]
    incident_id: str
    unit_type: str
    name: str
    parent_unit_id: Optional[int] = None
    sort_order: int = 0


@dataclass(slots=True)
class Position:
    """A position attached to a unit or to the command level."""

    id: Optional[int]
    incident_id: str
    title: str
    unit_id: Optional[int] = None
    sort_order: int = 0


@dataclass(slots=True)
class Assignment:
    """Snapshot of personnel assigned to a position."""

    id: Optional[int]
    incident_id: str
    position_id: int
    person_id: Optional[int] = None
    display_name: Optional[str] = None
    callsign: Optional[str] = None
    phone: Optional[str] = None
    agency: Optional[str] = None
    is_deputy: bool = False
    is_trainee: bool = False
    start_utc: Optional[str] = None
    end_utc: Optional[str] = None
    notes: Optional[str] = None


@dataclass(slots=True)
class AgencyRepresentative:
    """Agency representative associated with the incident."""

    id: Optional[int]
    incident_id: str
    name: str
    agency: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None


@dataclass(slots=True)
class OrgVersion:
    """Stored export/version metadata for ICS-203 snapshots."""

    id: Optional[int]
    incident_id: str
    label: str
    created_utc: str
    notes: Optional[str] = None
