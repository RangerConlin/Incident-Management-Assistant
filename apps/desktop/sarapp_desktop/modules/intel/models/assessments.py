"""Assessment dataclass for the Intel module."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


class AssessmentStatus:
    DRAFT = "Draft"
    IN_PROGRESS = "In Progress"
    COMPLETE = "Complete"
    ARCHIVED = "Archived"


ASSESSMENT_STATUSES = [
    AssessmentStatus.DRAFT,
    AssessmentStatus.IN_PROGRESS,
    AssessmentStatus.COMPLETE,
    AssessmentStatus.ARCHIVED,
]


@dataclass
class Assessment:
    id: str
    incident_id: str
    title: str
    status: str = AssessmentStatus.DRAFT
    analyst: Optional[str] = None
    summary: Optional[str] = None
    findings: Optional[str] = None
    recommendations: Optional[str] = None
    assessment_number: Optional[int] = None
    created_by: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    deleted: bool = False
    linked_subject_ids: list[str] = field(default_factory=list)
    linked_item_ids: list[str] = field(default_factory=list)

    @property
    def display_number(self) -> str:
        if self.assessment_number:
            return f"A-{self.assessment_number:03d}"
        return f"A-{self.id[:6].upper()}"

    @classmethod
    def from_api(cls, data: dict) -> "Assessment":
        return cls(
            id=data.get("_id") or data.get("id", ""),
            incident_id=data.get("incident_id", ""),
            title=data.get("title", "Untitled Assessment"),
            status=data.get("status", AssessmentStatus.DRAFT),
            analyst=data.get("analyst"),
            summary=data.get("summary"),
            findings=data.get("findings"),
            recommendations=data.get("recommendations"),
            assessment_number=data.get("assessment_number"),
            created_by=data.get("created_by"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            deleted=data.get("deleted", False),
            linked_subject_ids=data.get("linked_subject_ids", []),
            linked_item_ids=data.get("linked_item_ids", []),
        )

    def to_api_dict(self) -> dict:
        return {
            "title": self.title,
            "status": self.status,
            "analyst": self.analyst,
            "summary": self.summary,
            "findings": self.findings,
            "recommendations": self.recommendations,
            "linked_subject_ids": self.linked_subject_ids,
            "linked_item_ids": self.linked_item_ids,
            "created_by": self.created_by,
        }
