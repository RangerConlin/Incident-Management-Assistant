"""Domain models for the Logistics resource status board."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from utils.timefmt import abbreviate_tz_name


RESOURCE_STATUSES: tuple[str, ...] = (
    "Pending",
    "Enroute",
    "Checked In",
    "Assigned",
    "Available",
    "Out of Service",
    "Demobilized",
)

PENDING_STATUSES = {"Pending", "Enroute"}
ACTIVE_STATUSES = {"Checked In", "Assigned", "Available", "Out of Service"}
CLOSED_STATUSES = {"Demobilized"}


@dataclass(slots=True)
class ResourceItem:
    """A single tracked incident resource shown on the board."""

    id: str
    resource_id: str
    resource_name: str
    resource_type: str
    status: str
    eta_utc: Optional[str] = None
    assigned_to: Optional[str] = None
    assignment_reference: Optional[str] = None
    location: Optional[str] = None
    checked_in_time: Optional[str] = None
    last_updated: Optional[str] = None
    notes: Optional[str] = None
    source_entity_type: Optional[str] = None
    source_record_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_row(self) -> dict[str, object]:
        return {
            "id": self.id,
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "resource_type": self.resource_type,
            "status": self.status,
            "eta_utc": self.eta_utc,
            "assigned_to": self.assigned_to,
            "assignment_reference": self.assignment_reference,
            "location": self.location,
            "checked_in_time": self.checked_in_time,
            "last_updated": self.last_updated,
            "notes": self.notes,
            "source_entity_type": self.source_entity_type,
            "source_record_id": self.source_record_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "ResourceItem":
        return cls(
            id=str(row["id"]),
            resource_id=str(row.get("resource_id") or ""),
            resource_name=str(row.get("resource_name") or ""),
            resource_type=str(row.get("resource_type") or ""),
            status=normalize_status(str(row.get("status") or "")),
            eta_utc=_optional_text(row.get("eta_utc")),
            assigned_to=_optional_text(row.get("assigned_to")),
            assignment_reference=_optional_text(row.get("assignment_reference")),
            location=_optional_text(row.get("location")),
            checked_in_time=_optional_text(row.get("checked_in_time")),
            last_updated=_optional_text(row.get("last_updated")),
            notes=_optional_text(row.get("notes")),
            source_entity_type=_optional_text(row.get("source_entity_type")),
            source_record_id=_optional_text(row.get("source_record_id")),
            created_at=_optional_text(row.get("created_at")),
            updated_at=_optional_text(row.get("updated_at")),
        )

    @property
    def eta_overdue(self) -> bool:
        """Return ``True`` when the resource is overdue and not yet on-scene."""

        if self.status not in PENDING_STATUSES or not self.eta_utc:
            return False
        eta_dt = parse_datetime(self.eta_utc)
        if eta_dt is None:
            return False
        return eta_dt < datetime.now().astimezone()


@dataclass(slots=True)
class ResourceAuditEntry:
    """Audit trail row for resource status changes."""

    id: str
    resource_status_id: str
    field_name: str
    old_value: Optional[str]
    new_value: Optional[str]
    actor_name: Optional[str]
    changed_at: str

    def to_row(self) -> dict[str, object]:
        return {
            "id": self.id,
            "resource_status_id": self.resource_status_id,
            "field_name": self.field_name,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "actor_name": self.actor_name,
            "changed_at": self.changed_at,
        }


@dataclass(slots=True)
class ResourceBoardFilters:
    """User-selected filters applied by the resource status table."""

    status: Optional[str] = None
    resource_type: Optional[str] = None
    assignment: str = "All"
    eta_presence: str = "All"
    text_search: str = ""


def normalize_status(value: str) -> str:
    """Normalize legacy or loose values to the supported board statuses."""

    text = (value or "").strip()
    if not text:
        raise ValueError("Resource status is required")

    lowered = text.lower()
    mapping = {
        "pending": "Pending",
        "enroute": "Enroute",
        "en route": "Enroute",
        "checked in": "Checked In",
        "checked_in": "Checked In",
        "checkedin": "Checked In",
        "assigned": "Assigned",
        "available": "Available",
        "out of service": "Out of Service",
        "oos": "Out of Service",
        "demobilized": "Demobilized",
        "demob": "Demobilized",
    }
    normalized = mapping.get(lowered)
    if normalized is None and text in RESOURCE_STATUSES:
        normalized = text
    if normalized is None:
        raise ValueError(f"Unsupported resource status: {value}")
    return normalized


def parse_datetime(value: Any) -> Optional[datetime]:
    """Parse an ISO-like timestamp into a timezone-aware datetime when possible."""

    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.astimezone()
    text = str(value).strip()
    if not text:
        return None
    cleaned = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.astimezone()



def format_display_datetime(value: Any) -> str:
    """Return a user-friendly board timestamp string with short timezone (e.g., EDT)."""

    dt = parse_datetime(value)
    if dt is None:
        return ''
    local_dt = dt.astimezone()
    tz = abbreviate_tz_name(local_dt.tzname() or '')
    return f"{local_dt:%m-%d-%Y %H:%M} ({tz})"

def _optional_text(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    return str(value)
