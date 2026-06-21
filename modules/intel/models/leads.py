"""Lead dataclass for the Intel module."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


class LeadStatus:
    NEW = "New"
    ASSIGNED = "Assigned"
    IN_PROGRESS = "In Progress"
    CLOSED = "Closed"
    CONVERTED = "Converted"
    REJECTED = "Rejected"


class LeadPriority:
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class LeadSourceType:
    WITNESS = "Witness"
    TEAM_REPORT = "Team Report"
    PUBLIC_TIP = "Public Tip"
    ELECTRONIC = "Electronic"
    PHYSICAL_EVIDENCE = "Physical Evidence"
    SENSOR = "Sensor"
    LIAISON = "Liaison"
    OTHER = "Other"


LEAD_STATUSES = [
    LeadStatus.NEW,
    LeadStatus.ASSIGNED,
    LeadStatus.IN_PROGRESS,
    LeadStatus.CLOSED,
    LeadStatus.CONVERTED,
    LeadStatus.REJECTED,
]

LEAD_PRIORITIES = [
    LeadPriority.CRITICAL,
    LeadPriority.HIGH,
    LeadPriority.MEDIUM,
    LeadPriority.LOW,
]

LEAD_SOURCE_TYPES = [
    LeadSourceType.WITNESS,
    LeadSourceType.TEAM_REPORT,
    LeadSourceType.PUBLIC_TIP,
    LeadSourceType.ELECTRONIC,
    LeadSourceType.PHYSICAL_EVIDENCE,
    LeadSourceType.SENSOR,
    LeadSourceType.LIAISON,
    LeadSourceType.OTHER,
]


@dataclass
class Lead:
    id: str
    incident_id: str
    title: str
    status: str = LeadStatus.NEW
    priority: str = LeadPriority.MEDIUM
    source_type: str = LeadSourceType.OTHER
    summary: Optional[str] = None
    reported_by: Optional[str] = None
    contact_info: Optional[str] = None
    location_text: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_team_id: Optional[int] = None
    notes: Optional[str] = None
    lead_number: Optional[int] = None
    converted_to_type: Optional[str] = None
    converted_to_id: Optional[str] = None
    created_by: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    deleted: bool = False

    @property
    def display_number(self) -> str:
        if self.lead_number:
            return f"L-{self.lead_number:03d}"
        return f"L-{self.id[:6].upper()}"

    @property
    def is_open(self) -> bool:
        return self.status not in (LeadStatus.CLOSED, LeadStatus.CONVERTED, LeadStatus.REJECTED)

    @classmethod
    def from_api(cls, data: dict) -> "Lead":
        return cls(
            id=data.get("_id") or data.get("id", ""),
            incident_id=data.get("incident_id", ""),
            title=data.get("title", "Untitled Lead"),
            status=data.get("status", LeadStatus.NEW),
            priority=data.get("priority", LeadPriority.MEDIUM),
            source_type=data.get("source_type", LeadSourceType.OTHER),
            summary=data.get("summary"),
            reported_by=data.get("reported_by"),
            contact_info=data.get("contact_info"),
            location_text=data.get("location_text"),
            assigned_to=data.get("assigned_to"),
            assigned_team_id=data.get("assigned_team_id"),
            notes=data.get("notes"),
            lead_number=data.get("lead_number"),
            converted_to_type=data.get("converted_to_type"),
            converted_to_id=data.get("converted_to_id"),
            created_by=data.get("created_by"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            deleted=data.get("deleted", False),
        )

    def to_api_dict(self) -> dict:
        return {
            "title": self.title,
            "status": self.status,
            "priority": self.priority,
            "source_type": self.source_type,
            "summary": self.summary,
            "reported_by": self.reported_by,
            "contact_info": self.contact_info,
            "location_text": self.location_text,
            "assigned_to": self.assigned_to,
            "assigned_team_id": self.assigned_team_id,
            "notes": self.notes,
        }
