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


class LeadSourceCategory:
    TEAM = "Team"
    STAFF = "Staff"
    AGENCY_LIAISON = "Agency / Liaison"
    PUBLIC_TIP = "Public Tip"
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

LEAD_SOURCE_CATEGORIES = [
    LeadSourceCategory.TEAM,
    LeadSourceCategory.STAFF,
    LeadSourceCategory.AGENCY_LIAISON,
    LeadSourceCategory.PUBLIC_TIP,
    LeadSourceCategory.OTHER,
]

SOURCE_RELIABILITY_VALUES = [
    "Unknown",
    "Firsthand",
    "Secondhand",
    "Official",
    "Unverified",
    "Questionable",
]

INFORMATION_CONFIDENCE_VALUES = [
    "Confirmed",
    "Probable",
    "Possible",
    "Unconfirmed",
    "Ruled Out",
]

_CATEGORY_TO_SOURCE_TYPE = {
    LeadSourceCategory.TEAM: LeadSourceType.TEAM_REPORT,
    LeadSourceCategory.STAFF: LeadSourceType.TEAM_REPORT,
    LeadSourceCategory.AGENCY_LIAISON: LeadSourceType.LIAISON,
    LeadSourceCategory.PUBLIC_TIP: LeadSourceType.PUBLIC_TIP,
    LeadSourceCategory.OTHER: LeadSourceType.OTHER,
}


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

    # Structured source fields
    source_category: Optional[str] = None
    source_display: Optional[str] = None
    source_ref_type: Optional[str] = None
    source_ref_id: Optional[str] = None
    source_subject_id: Optional[str] = None
    source_team_id: Optional[int] = None
    source_team_name: Optional[str] = None
    source_staff_id: Optional[str] = None
    source_agency: Optional[str] = None
    source_role: Optional[str] = None
    source_contact_name: Optional[str] = None
    source_phone: Optional[str] = None
    source_email: Optional[str] = None
    source_address: Optional[str] = None
    source_contact_method: Optional[str] = None
    source_notes: Optional[str] = None

    # Report-quality fields
    source_reliability: Optional[str] = None
    information_confidence: Optional[str] = None

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
            source_category=data.get("source_category"),
            source_display=data.get("source_display"),
            source_ref_type=data.get("source_ref_type"),
            source_ref_id=data.get("source_ref_id"),
            source_subject_id=data.get("source_subject_id"),
            source_team_id=data.get("source_team_id"),
            source_team_name=data.get("source_team_name"),
            source_staff_id=data.get("source_staff_id"),
            source_agency=data.get("source_agency"),
            source_role=data.get("source_role"),
            source_contact_name=data.get("source_contact_name"),
            source_phone=data.get("source_phone"),
            source_email=data.get("source_email"),
            source_address=data.get("source_address"),
            source_contact_method=data.get("source_contact_method"),
            source_notes=data.get("source_notes"),
            source_reliability=data.get("source_reliability"),
            information_confidence=data.get("information_confidence"),
        )

    def to_api_dict(self) -> dict:
        # Populate legacy reported_by/contact_info from structured fields when blank
        reported_by = self.reported_by
        if not reported_by:
            reported_by = self.source_contact_name or self.source_display or None

        contact_info = self.contact_info
        if not contact_info:
            parts = [p for p in (self.source_phone, self.source_email, self.source_contact_method) if p]
            contact_info = " / ".join(parts) or None

        return {
            "title": self.title,
            "status": self.status,
            "priority": self.priority,
            "source_type": self.source_type,
            "summary": self.summary,
            "reported_by": reported_by,
            "contact_info": contact_info,
            "location_text": self.location_text,
            "assigned_to": self.assigned_to,
            "assigned_team_id": self.assigned_team_id,
            "notes": self.notes,
            # Structured source
            "source_category": self.source_category,
            "source_display": self.source_display,
            "source_ref_type": self.source_ref_type,
            "source_ref_id": self.source_ref_id,
            "source_subject_id": self.source_subject_id,
            "source_team_id": self.source_team_id,
            "source_team_name": self.source_team_name,
            "source_staff_id": self.source_staff_id,
            "source_agency": self.source_agency,
            "source_role": self.source_role,
            "source_contact_name": self.source_contact_name,
            "source_phone": self.source_phone,
            "source_email": self.source_email,
            "source_address": self.source_address,
            "source_contact_method": self.source_contact_method,
            "source_notes": self.source_notes,
            "source_reliability": self.source_reliability,
            "information_confidence": self.information_confidence,
        }
