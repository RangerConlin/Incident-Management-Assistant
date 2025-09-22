"""Domain models for the Logistics Check-In module."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class CIStatus(str, Enum):
    """Canonical Check-In status values used within the UI and DB."""

    CHECKED_IN = "CheckedIn"
    PENDING = "Pending"
    AT_ICP = "AtICP"
    OFF_DUTY = "OffDuty"
    DEMOBILIZED = "Demobilized"
    NO_SHOW = "NoShow"

    @classmethod
    def normalize(cls, value: str) -> "CIStatus":
        """Return a canonical status from user or legacy values."""
        if not value:
            raise ValueError("Check-In status is required")
        value = value.strip()
        mapping = {
            "Enroute to Incident": cls.PENDING,
            "EnrouteToIncident": cls.PENDING,
            "Enroute": cls.PENDING,
        }
        if value in mapping:
            return mapping[value]
        try:
            return cls(value)
        except ValueError as exc:  # pragma: no cover - defensive guard
            raise ValueError(f"Unsupported Check-In status: {value}") from exc

    @classmethod
    def choices(cls) -> tuple["CIStatus", ...]:
        return tuple(cls)


class PersonnelStatus(str, Enum):
    """Personnel status values stored in the incident database."""

    AVAILABLE = "Available"
    ASSIGNED = "Assigned"
    PENDING = "Pending"
    UNAVAILABLE = "Unavailable"
    DEMOBILIZED = "Demobilized"

    @classmethod
    def normalize(cls, value: str) -> "PersonnelStatus":
        if not value:
            raise ValueError("Personnel status is required")
        try:
            return cls(value)
        except ValueError as exc:  # pragma: no cover - defensive guard
            raise ValueError(f"Unsupported personnel status: {value}") from exc

    @classmethod
    def choices(cls) -> tuple["PersonnelStatus", ...]:
        return tuple(cls)


class Location(str, Enum):
    """Incident location options supported by the UI."""

    ICP = "ICP"
    STAGING = "Staging"
    HELIBASE = "Helibase"
    OTHER = "Other"

    @classmethod
    def normalize(cls, value: str) -> "Location":
        if not value:
            raise ValueError("Location is required")
        try:
            return cls(value)
        except ValueError as exc:  # pragma: no cover - defensive guard
            raise ValueError(f"Unsupported location: {value}") from exc

    @classmethod
    def choices(cls) -> tuple["Location", ...]:
        return tuple(cls)


@dataclass(slots=True)
class UIFlags:
    """Flags consumed by the Qt layer for row rendering."""

    hidden_by_default: bool = False
    grayed: bool = False

    def to_dict(self) -> Dict[str, bool]:
        return {"hidden_by_default": self.hidden_by_default, "grayed": self.grayed}


@dataclass(slots=True)
class PersonnelIdentity:
    """Read-only person identity from ``master.db``."""

    person_id: str
    name: str
    primary_role: Optional[str] = None
    phone: Optional[str] = None
    callsign: Optional[str] = None
    certifications: Optional[str] = None
    home_unit: Optional[str] = None

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "PersonnelIdentity":
        return cls(
            person_id=row["id"],
            name=row.get("name") or "",
            primary_role=row.get("primary_role"),
            phone=row.get("phone"),
            callsign=row.get("callsign"),
            certifications=row.get("certifications"),
            home_unit=row.get("home_unit"),
        )


@dataclass(slots=True)
class CheckInRecord:
    """A persisted incident check-in row."""

    person_id: str
    ci_status: CIStatus
    personnel_status: PersonnelStatus
    arrival_time: str
    location: Location
    location_other: Optional[str] = None
    shift_start: Optional[str] = None
    shift_end: Optional[str] = None
    notes: Optional[str] = None
    incident_callsign: Optional[str] = None
    incident_phone: Optional[str] = None
    team_id: Optional[str] = None
    role_on_team: Optional[str] = None
    operational_period: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().astimezone().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().astimezone().isoformat())
    ui_flags: UIFlags = field(default_factory=UIFlags)
    pending: bool = False

    def to_payload(self) -> Dict[str, Any]:
        return {
            "person_id": self.person_id,
            "ci_status": self.ci_status.value,
            "personnel_status": self.personnel_status.value,
            "arrival_time": self.arrival_time,
            "location": self.location.value,
            "location_other": self.location_other,
            "shift_start": self.shift_start,
            "shift_end": self.shift_end,
            "notes": self.notes,
            "incident_callsign": self.incident_callsign,
            "incident_phone": self.incident_phone,
            "team_id": self.team_id,
            "role_on_team": self.role_on_team,
            "operational_period": self.operational_period,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "CheckInRecord":
        return cls(
            person_id=row["person_id"],
            ci_status=CIStatus.normalize(row["ci_status"]),
            personnel_status=PersonnelStatus.normalize(row["personnel_status"]),
            arrival_time=row["arrival_time"],
            location=Location.normalize(row["location"]),
            location_other=row.get("location_other"),
            shift_start=row.get("shift_start"),
            shift_end=row.get("shift_end"),
            notes=row.get("notes"),
            incident_callsign=row.get("incident_callsign"),
            incident_phone=row.get("incident_phone"),
            team_id=row.get("team_id"),
            role_on_team=row.get("role_on_team"),
            operational_period=row.get("operational_period"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
            ui_flags=UIFlags(
                hidden_by_default=bool(row.get("hidden_by_default", False)),
                grayed=bool(row.get("grayed", False)),
            ),
            pending=bool(row.get("pending", False)),
        )


@dataclass(slots=True)
class RosterRow:
    """Row returned by ``getRoster`` for the roster table."""

    person_id: str
    name: str
    role: Optional[str]
    team: Optional[str]
    phone: Optional[str]
    callsign: Optional[str]
    ci_status: CIStatus
    personnel_status: PersonnelStatus
    updated_at: str
    team_id: Optional[str] = None
    row_class: Optional[str] = None
    ui_flags: UIFlags = field(default_factory=UIFlags)

    def as_table_row(self) -> Dict[str, Any]:
        return {
            "person_id": self.person_id,
            "name": self.name,
            "role": self.role,
            "team": self.team,
            "phone": self.phone,
            "callsign": self.callsign,
            "ci_status": self.ci_status.value,
            "personnel_status": self.personnel_status.value,
            "updated_at": self.updated_at,
            "team_id": self.team_id,
            "row_class": self.row_class,
            "ui_flags": self.ui_flags.to_dict(),
        }


@dataclass(slots=True)
class HistoryItem:
    """Event stored in the incident history table."""

    id: int
    ts: str
    actor: str
    event_type: str
    payload: Dict[str, Any]


@dataclass(slots=True)
class CheckInUpsert:
    """Payload accepted by :func:`upsertCheckIn`."""

    person_id: str
    ci_status: CIStatus
    arrival_time: str
    location: Location
    location_other: Optional[str] = None
    shift_start: Optional[str] = None
    shift_end: Optional[str] = None
    notes: Optional[str] = None
    incident_callsign: Optional[str] = None
    incident_phone: Optional[str] = None
    team_id: Optional[str] = None
    role_on_team: Optional[str] = None
    operational_period: Optional[str] = None
    expected_updated_at: Optional[str] = None
    override_personnel_status: Optional[PersonnelStatus] = None
    override_reason: Optional[str] = None

    def to_record(self, base: Optional[CheckInRecord] = None) -> CheckInRecord:
        """Merge the upsert payload into an existing record."""
        if base is None:
            created_at = datetime.now().astimezone().isoformat()
        else:
            created_at = base.created_at
        updated_at = datetime.now().astimezone().isoformat()
        personnel_status = (
            self.override_personnel_status or (base.personnel_status if base else PersonnelStatus.PENDING)
        )
        record = CheckInRecord(
            person_id=self.person_id,
            ci_status=self.ci_status,
            personnel_status=personnel_status,
            arrival_time=self.arrival_time,
            location=self.location,
            location_other=self.location_other,
            shift_start=self.shift_start,
            shift_end=self.shift_end,
            notes=self.notes,
            incident_callsign=self.incident_callsign,
            incident_phone=self.incident_phone,
            team_id=self.team_id,
            role_on_team=self.role_on_team,
            operational_period=self.operational_period,
            created_at=created_at,
            updated_at=updated_at,
        )
        if base is not None:
            # Carry forward unset optional fields from the base record
            for field_name in (
                "location_other",
                "shift_start",
                "shift_end",
                "notes",
                "incident_callsign",
                "incident_phone",
                "team_id",
                "role_on_team",
                "operational_period",
            ):
                value = getattr(record, field_name)
                if value is None:
                    setattr(record, field_name, getattr(base, field_name))
        return record

    def to_queue_payload(self) -> Dict[str, Any]:
        payload = {
            "person_id": self.person_id,
            "ci_status": self.ci_status.value,
            "arrival_time": self.arrival_time,
            "location": self.location.value,
            "location_other": self.location_other,
            "shift_start": self.shift_start,
            "shift_end": self.shift_end,
            "notes": self.notes,
            "incident_callsign": self.incident_callsign,
            "incident_phone": self.incident_phone,
            "team_id": self.team_id,
            "role_on_team": self.role_on_team,
            "operational_period": self.operational_period,
            "expected_updated_at": self.expected_updated_at,
        }
        if self.override_personnel_status:
            payload["override_personnel_status"] = self.override_personnel_status.value
        if self.override_reason:
            payload["override_reason"] = self.override_reason
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "CheckInUpsert":
        return cls(
            person_id=payload["person_id"],
            ci_status=CIStatus.normalize(payload["ci_status"]),
            arrival_time=payload["arrival_time"],
            location=Location.normalize(payload["location"]),
            location_other=payload.get("location_other"),
            shift_start=payload.get("shift_start"),
            shift_end=payload.get("shift_end"),
            notes=payload.get("notes"),
            incident_callsign=payload.get("incident_callsign"),
            incident_phone=payload.get("incident_phone"),
            team_id=payload.get("team_id"),
            role_on_team=payload.get("role_on_team"),
            operational_period=payload.get("operational_period"),
            expected_updated_at=payload.get("expected_updated_at"),
            override_personnel_status=(
                PersonnelStatus.normalize(payload["override_personnel_status"])
                if payload.get("override_personnel_status")
                else None
            ),
            override_reason=payload.get("override_reason"),
        )


@dataclass(slots=True)
class RosterFilters:
    """Filters accepted by :func:`getRoster`."""

    q: Optional[str] = None
    ci_status: Optional[CIStatus] = None
    personnel_status: Optional[PersonnelStatus] = None
    role: Optional[str] = None
    team: Optional[str] = None
    include_no_show: bool = False

    def apply_defaults(self) -> None:
        if self.q:
            self.q = self.q.strip()
        if self.role == "All":
            self.role = None
        if self.team in {"All", "—", ""}:
            self.team = None

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "RosterFilters":
        ci_status = payload.get("ci_status")
        personnel_status = payload.get("personnel_status")
        return cls(
            q=payload.get("q") or None,
            ci_status=CIStatus.normalize(ci_status) if ci_status and ci_status != "All" else None,
            personnel_status=(
                PersonnelStatus.normalize(personnel_status)
                if personnel_status and personnel_status != "All"
                else None
            ),
            role=(payload.get("role") if payload.get("role") not in (None, "All") else None),
            team=(payload.get("team") if payload.get("team") not in (None, "All") else None),
            include_no_show=bool(payload.get("include_no_show")),
        )


@dataclass(slots=True)
class QueueItem:
    """Item stored in the offline queue."""

    op: str
    payload: Dict[str, Any]
    ts: str

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "QueueItem":
        return cls(op=payload["op"], payload=payload["payload"], ts=payload["ts"])

    def to_dict(self) -> Dict[str, Any]:
        return {"op": self.op, "payload": self.payload, "ts": self.ts}


__all__ = [
    "CIStatus",
    "PersonnelStatus",
    "Location",
    "UIFlags",
    "PersonnelIdentity",
    "CheckInRecord",
    "RosterRow",
    "HistoryItem",
    "CheckInUpsert",
    "RosterFilters",
    "QueueItem",
]
