"""IntelLogEntry dataclass for the Intel module."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


_ENTITY_LABELS = {
    "subject":    "Subject",
    "lead":       "Lead",
    "item":       "Intel Item",
    "assessment": "Assessment",
    "report":     "Report",
    "observation": "Observation",
    "attachment": "Attachment",
    "form":       "Form",
}

_EVENT_LABELS = {
    "created":             "Created",
    "updated":             "Updated",
    "archived":            "Archived",
    "deleted":             "Deleted",
    "converted":           "Converted",
    "closed":              "Closed",
    "completed":           "Completed",
    "rejected":            "Rejected",
    "reopened":            "Reopened",
    "assigned":            "Assigned",
    "status_changed":      "Status Changed",
    "priority_changed":    "Priority Changed",
    "linked":              "Linked",
    "unlinked":            "Unlinked",
    "observation_added":   "Observation Added",
    "observation_updated": "Observation Updated",
    "attachment_added":    "Attachment Added",
    "attachment_removed":  "Attachment Removed",
    "form_linked":         "Form Linked",
    "form_unlinked":       "Form Unlinked",
}


@dataclass
class IntelLogEntry:
    id: str
    incident_id: str
    entity_type: str
    entity_id: str
    event_type: str
    summary: str
    actor: Optional[str] = None
    timestamp: str = ""

    @property
    def entity_label(self) -> str:
        return _ENTITY_LABELS.get(self.entity_type, self.entity_type.title())

    @property
    def event_label(self) -> str:
        return _EVENT_LABELS.get(self.event_type, self.event_type.replace("_", " ").title())

    @classmethod
    def from_api(cls, data: dict) -> "IntelLogEntry":
        return cls(
            id=data.get("_id") or data.get("id", ""),
            incident_id=data.get("incident_id", ""),
            entity_type=data.get("entity_type", ""),
            entity_id=data.get("entity_id", ""),
            event_type=data.get("event_type", ""),
            summary=data.get("summary", ""),
            actor=data.get("actor"),
            timestamp=data.get("timestamp") or data.get("logged_at", ""),
        )
