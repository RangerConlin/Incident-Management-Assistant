"""IntelItem and Observation dataclasses for the Intel module."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

ITEM_TYPES = [
    "Clue",
    "Infrastructure Assessment",
    "Road Closure",
    "Hazard",
    "Resource Status",
    "Population Movement",
    "Communications",
    "Medical",
    "Environmental",
    "Other",
]

PRIORITY_VALUES = ["Critical", "High", "Medium", "Low"]
CONFIDENCE_VALUES = ["Confirmed", "Probable", "Possible", "Unconfirmed", "Ruled Out"]
TREND_VALUES = ["Improving", "Stable", "Worsening", "Unknown"]
SEVERITY_VALUES = ["Critical", "High", "Medium", "Low", "None"]
STATUS_VALUES = ["Active", "Closed", "Archived"]


@dataclass
class Observation:
    obs_id: str
    observed_at: str
    observer: str
    status: str = "Active"
    severity: str = "Low"
    confidence: str = "Possible"
    summary: str = ""
    source_team: Optional[str] = None
    source_team_id: Optional[int] = None
    detailed_notes: Optional[str] = None
    location_text: Optional[str] = None
    attachments: list[str] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict) -> "Observation":
        return cls(
            obs_id=data.get("obs_id", ""),
            observed_at=data.get("observed_at", ""),
            observer=data.get("observer", ""),
            status=data.get("status", "Active"),
            severity=data.get("severity", "Low"),
            confidence=data.get("confidence", "Possible"),
            summary=data.get("summary", ""),
            source_team=data.get("source_team"),
            source_team_id=data.get("source_team_id"),
            detailed_notes=data.get("detailed_notes"),
            location_text=data.get("location_text"),
            attachments=data.get("attachments", []),
        )

    def to_api_dict(self) -> dict:
        return {
            "observed_at": self.observed_at,
            "observer": self.observer,
            "status": self.status,
            "severity": self.severity,
            "confidence": self.confidence,
            "summary": self.summary,
            "source_team": self.source_team,
            "source_team_id": self.source_team_id,
            "detailed_notes": self.detailed_notes,
            "location_text": self.location_text,
            "attachments": self.attachments,
        }


@dataclass
class IntelItem:
    id: str
    incident_id: str
    item_type: str
    title: str
    status: str = "Active"
    priority: str = "Medium"
    confidence: str = "Possible"
    trend: str = "Unknown"
    location_text: Optional[str] = None
    notes: Optional[str] = None
    source_lead_id: Optional[str] = None
    created_by: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    deleted: bool = False
    observations: list[Observation] = field(default_factory=list)
    linked_subject_ids: list[str] = field(default_factory=list)
    linked_task_ids: list[str] = field(default_factory=list)
    linked_team_ids: list[int] = field(default_factory=list)

    @property
    def observation_count(self) -> int:
        return len(self.observations)

    @property
    def latest_observation(self) -> Optional[Observation]:
        if not self.observations:
            return None
        return max(self.observations, key=lambda o: o.observed_at)

    @classmethod
    def from_api(cls, data: dict) -> "IntelItem":
        obs_raw = data.get("observations", [])
        observations = [Observation.from_api(o) for o in obs_raw]
        return cls(
            id=data.get("_id") or data.get("id", ""),
            incident_id=data.get("incident_id", ""),
            item_type=data.get("item_type", "Other"),
            title=data.get("title", "Untitled"),
            status=data.get("status", "Active"),
            priority=data.get("priority", "Medium"),
            confidence=data.get("confidence", "Possible"),
            trend=data.get("trend", "Unknown"),
            location_text=data.get("location_text"),
            notes=data.get("notes"),
            source_lead_id=data.get("source_lead_id"),
            created_by=data.get("created_by"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            deleted=data.get("deleted", False),
            observations=observations,
            linked_subject_ids=data.get("linked_subject_ids", []),
            linked_task_ids=data.get("linked_task_ids", []),
            linked_team_ids=data.get("linked_team_ids", []),
        )

    def to_api_dict(self) -> dict:
        return {
            "item_type": self.item_type,
            "title": self.title,
            "status": self.status,
            "priority": self.priority,
            "confidence": self.confidence,
            "trend": self.trend,
            "location_text": self.location_text,
            "notes": self.notes,
            "source_lead_id": self.source_lead_id,
            "linked_subject_ids": self.linked_subject_ids,
            "linked_task_ids": self.linked_task_ids,
            "linked_team_ids": self.linked_team_ids,
        }
