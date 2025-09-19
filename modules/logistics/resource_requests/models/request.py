"""Dataclasses representing resource requests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

from .enums import Priority, RequestStatus

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def utcnow() -> str:
    """Return a UTC timestamp in ISO-8601 with Z suffix."""

    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


@dataclass(slots=True)
class ResourceRequest:
    id: str
    incident_id: str
    title: str
    requesting_section: str
    priority: Priority
    status: RequestStatus
    created_by_id: str
    created_utc: str
    last_updated_utc: str
    needed_by_utc: Optional[str] = None
    justification: Optional[str] = None
    delivery_location: Optional[str] = None
    comms_requirements: Optional[str] = None
    links: Optional[str] = None
    version: int = 1

    def to_row(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "title": self.title,
            "requesting_section": self.requesting_section,
            "needed_by_utc": self.needed_by_utc,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_utc": self.created_utc,
            "created_by_id": self.created_by_id,
            "last_updated_utc": self.last_updated_utc,
            "justification": self.justification,
            "delivery_location": self.delivery_location,
            "comms_requirements": self.comms_requirements,
            "links": self.links,
            "version": self.version,
        }

    @classmethod
    def from_row(cls, row: Dict[str, object]) -> "ResourceRequest":
        return cls(
            id=row["id"],
            incident_id=row["incident_id"],
            title=row["title"],
            requesting_section=row["requesting_section"],
            priority=Priority(row["priority"]),
            status=RequestStatus(row["status"]),
            created_by_id=row["created_by_id"],
            created_utc=row["created_utc"],
            last_updated_utc=row["last_updated_utc"],
            needed_by_utc=row.get("needed_by_utc"),
            justification=row.get("justification"),
            delivery_location=row.get("delivery_location"),
            comms_requirements=row.get("comms_requirements"),
            links=row.get("links"),
            version=row.get("version", 1),
        )


def create_from_header(request_id: str, incident_id: str, header: Dict[str, object]) -> ResourceRequest:
    """Construct a :class:`ResourceRequest` from raw header data."""

    now = utcnow()
    status_value = header.get("status", RequestStatus.DRAFT.value)
    if isinstance(status_value, RequestStatus):
        status = status_value
    else:
        status = RequestStatus(str(status_value).upper())

    return ResourceRequest(
        id=request_id,
        incident_id=incident_id,
        title=str(header["title"]),
        requesting_section=str(header["requesting_section"]),
        priority=Priority(str(header["priority"]).upper()),
        status=status,
        created_by_id=str(header.get("created_by_id", "unknown")),
        created_utc=header.get("created_utc", now),
        last_updated_utc=header.get("last_updated_utc", now),
        needed_by_utc=header.get("needed_by_utc"),
        justification=header.get("justification"),
        delivery_location=header.get("delivery_location"),
        comms_requirements=header.get("comms_requirements"),
        links=header.get("links"),
        version=int(header.get("version", 1)),
    )
