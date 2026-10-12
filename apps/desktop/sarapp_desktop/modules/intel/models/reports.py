"""IntelReport dataclass for the Intel module."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

REPORT_TYPES = [
    "Situation Report",
    "Intelligence Summary",
    "Subject Profile",
    "Area Assessment",
    "Incident Action Plan Support",
    "Briefing",
    "Other",
]


@dataclass
class IntelReport:
    id: str
    incident_id: str
    title: str
    report_type: str = "Situation Report"
    status: str = "Draft"
    body_markdown: Optional[str] = None
    report_number: Optional[int] = None
    created_by: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    deleted: bool = False
    linked_subject_ids: list[str] = field(default_factory=list)
    linked_item_ids: list[str] = field(default_factory=list)
    linked_assessment_ids: list[str] = field(default_factory=list)

    @property
    def display_number(self) -> str:
        if self.report_number:
            return f"R-{self.report_number:03d}"
        return f"R-{self.id[:6].upper()}"

    @classmethod
    def from_api(cls, data: dict) -> "IntelReport":
        return cls(
            id=data.get("_id") or data.get("id", ""),
            incident_id=data.get("incident_id", ""),
            title=data.get("title", "Untitled Report"),
            report_type=data.get("report_type", "Situation Report"),
            status=data.get("status", "Draft"),
            body_markdown=data.get("body_markdown"),
            report_number=data.get("report_number"),
            created_by=data.get("created_by"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            deleted=data.get("deleted", False),
            linked_subject_ids=data.get("linked_subject_ids", []),
            linked_item_ids=data.get("linked_item_ids", []),
            linked_assessment_ids=data.get("linked_assessment_ids", []),
        )

    def to_api_dict(self) -> dict:
        return {
            "title": self.title,
            "report_type": self.report_type,
            "status": self.status,
            "body_markdown": self.body_markdown,
        }
