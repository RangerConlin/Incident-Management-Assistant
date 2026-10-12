"""Data models and API client helpers for the SITREP module."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from utils.api_client import api_client, APIError


SITREP_STATUSES = [
    ("draft", "Draft"),
    ("ready_for_review", "Ready for Review"),
    ("needs_revision", "Needs Revision"),
    ("approved", "Approved"),
    ("distributed", "Distributed"),
    ("archived", "Archived"),
]

AUDIENCES = [
    ("internal", "Internal"),
    ("agency", "Agency Partner"),
    ("public", "Public-Safe"),
    ("custom", "Custom"),
]

TEMPOS = [
    ("stable", "Stable"),
    ("escalating", "Escalating"),
    ("de_escalating", "De-escalating"),
    ("transitioning", "Transitioning"),
]

VISIBILITIES = [
    ("internal", "Internal"),
    ("agency", "Agency"),
    ("public", "Public"),
    ("sensitive", "Sensitive"),
]

REVIEW_STATUSES = [
    ("auto_filled", "Auto-filled"),
    ("edited", "Edited"),
    ("needs_review", "Needs Review"),
    ("reviewed", "Reviewed"),
    ("excluded", "Excluded"),
]

EVENT_TYPES = [
    "Command Decision",
    "Operational Change",
    "Assignment Change",
    "Resource Change",
    "Safety Issue",
    "Weather Change",
    "Clue / Lead",
    "Subject Update",
    "Agency Coordination",
    "Public Information",
    "Communications",
    "Logistics",
    "Medical",
]

IMPACT_LEVELS = ["low", "medium", "high", "critical"]

MVP_SECTION_TYPES = [
    "situation_overview",
    "operational_status",
    "significant_changes",
    "safety_hazards",
    "resource_status",
    "communications_status",
    "liaison_coordination",
    "needs_decisions",
    "next_update",
]

SECTION_TITLES = {
    "situation_overview": "Situation Overview",
    "operational_status": "Operational Status",
    "significant_changes": "Significant Changes",
    "safety_hazards": "Safety / Hazards",
    "resource_status": "Resource Status",
    "communications_status": "Communications Status",
    "liaison_coordination": "Liaison / Agency Coordination",
    "needs_decisions": "Needs / Decisions",
    "next_update": "Next Update",
}


@dataclass
class SitrepSection:
    section_type: str
    title: str
    auto_content: str = ""
    edited_content: str = ""
    visibility: str = "internal"
    review_status: str = "auto_filled"
    last_refreshed_at: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "SitrepSection":
        return cls(
            section_type=d.get("section_type", ""),
            title=d.get("title", ""),
            auto_content=d.get("auto_content", ""),
            edited_content=d.get("edited_content", ""),
            visibility=d.get("visibility", "internal"),
            review_status=d.get("review_status", "auto_filled"),
            last_refreshed_at=d.get("last_refreshed_at"),
        )

    def to_dict(self) -> dict:
        return {
            "section_type": self.section_type,
            "title": self.title,
            "auto_content": self.auto_content,
            "edited_content": self.edited_content,
            "visibility": self.visibility,
            "review_status": self.review_status,
            "last_refreshed_at": self.last_refreshed_at,
        }

    @property
    def display_content(self) -> str:
        return self.edited_content or self.auto_content


@dataclass
class SitrepSummary:
    id: str
    incident_id: str
    sitrep_number: int
    status: str
    audience: str
    prepared_by: str
    created_at: str
    updated_at: str
    summary: str
    current_priority: str = ""
    current_tempo: str = "stable"
    next_update_due: Optional[str] = None
    approved_by: Optional[str] = None
    operational_period_id: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "SitrepSummary":
        return cls(
            id=d.get("id", ""),
            incident_id=d.get("incident_id", ""),
            sitrep_number=d.get("sitrep_number", 0),
            status=d.get("status", "draft"),
            audience=d.get("audience", "internal"),
            prepared_by=d.get("prepared_by", ""),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            summary=d.get("summary", ""),
            current_priority=d.get("current_priority", ""),
            current_tempo=d.get("current_tempo", "stable"),
            next_update_due=d.get("next_update_due"),
            approved_by=d.get("approved_by"),
            operational_period_id=d.get("operational_period_id"),
        )


@dataclass
class Sitrep(SitrepSummary):
    sections: list[SitrepSection] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "Sitrep":  # type: ignore[override]
        sections = [SitrepSection.from_dict(s) for s in d.get("sections", [])]
        return cls(
            id=d.get("id", ""),
            incident_id=d.get("incident_id", ""),
            sitrep_number=d.get("sitrep_number", 0),
            status=d.get("status", "draft"),
            audience=d.get("audience", "internal"),
            prepared_by=d.get("prepared_by", ""),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            summary=d.get("summary", ""),
            current_priority=d.get("current_priority", ""),
            current_tempo=d.get("current_tempo", "stable"),
            next_update_due=d.get("next_update_due"),
            approved_by=d.get("approved_by"),
            operational_period_id=d.get("operational_period_id"),
            sections=sections,
        )

    def section(self, section_type: str) -> Optional[SitrepSection]:
        for s in self.sections:
            if s.section_type == section_type:
                return s
        return None


@dataclass
class SitrepEvent:
    id: str
    incident_id: str
    timestamp: str
    event_type: str
    summary: str
    source: str
    impact: str
    visibility: str
    include_in_sitrep: bool
    include_in_214: bool
    notes: str = ""
    sitrep_id: Optional[str] = None
    reviewed_by: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "SitrepEvent":
        return cls(
            id=d.get("id", ""),
            incident_id=d.get("incident_id", ""),
            timestamp=d.get("timestamp", ""),
            event_type=d.get("event_type", ""),
            summary=d.get("summary", ""),
            source=d.get("source", ""),
            impact=d.get("impact", "low"),
            visibility=d.get("visibility", "internal"),
            include_in_sitrep=d.get("include_in_sitrep", True),
            include_in_214=d.get("include_in_214", False),
            notes=d.get("notes", ""),
            sitrep_id=d.get("sitrep_id"),
            reviewed_by=d.get("reviewed_by"),
        )


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

class SitrepApiClient:
    def __init__(self, incident_id: str) -> None:
        self._incident_id = incident_id
        self._prefix = f"/api/incidents/{incident_id}"

    def list_sitreps(self) -> list[SitrepSummary]:
        data = api_client.get(f"{self._prefix}/sitreps")
        return [SitrepSummary.from_dict(d) for d in (data or [])]

    def get_sitrep(self, sitrep_id: str) -> Sitrep:
        data = api_client.get(f"{self._prefix}/sitreps/{sitrep_id}")
        return Sitrep.from_dict(data)

    def create_sitrep(self, payload: dict) -> Sitrep:
        data = api_client.post(f"{self._prefix}/sitreps", json=payload)
        return Sitrep.from_dict(data)

    def update_sitrep(self, sitrep_id: str, payload: dict) -> Sitrep:
        data = api_client.patch(f"{self._prefix}/sitreps/{sitrep_id}", json=payload)
        return Sitrep.from_dict(data)

    def duplicate_sitrep(self, sitrep_id: str, payload: Optional[dict] = None) -> Sitrep:
        data = api_client.post(
            f"{self._prefix}/sitreps/{sitrep_id}/duplicate",
            json=payload or {},
        )
        return Sitrep.from_dict(data)

    def refresh_sitrep(self, sitrep_id: str) -> Sitrep:
        """Re-pull live module data into the SITREP's auto-filled sections."""
        data = api_client.post(f"{self._prefix}/sitreps/{sitrep_id}/refresh", json={})
        return Sitrep.from_dict(data)

    def delete_sitrep(self, sitrep_id: str) -> None:
        api_client.delete(f"{self._prefix}/sitreps/{sitrep_id}")

    def get_operational_summary(self) -> dict:
        return api_client.get(f"{self._prefix}/sitreps/operational-summary") or {}

    def list_events(self, sitrep_id: Optional[str] = None) -> list[SitrepEvent]:
        params: dict[str, Any] = {}
        if sitrep_id:
            params["sitrep_id"] = sitrep_id
        data = api_client.get(f"{self._prefix}/sitrep-events", params=params)
        return [SitrepEvent.from_dict(d) for d in (data or [])]

    def create_event(self, payload: dict) -> SitrepEvent:
        data = api_client.post(f"{self._prefix}/sitrep-events", json=payload)
        return SitrepEvent.from_dict(data)

    def update_event(self, event_id: str, payload: dict) -> SitrepEvent:
        data = api_client.patch(f"{self._prefix}/sitrep-events/{event_id}", json=payload)
        return SitrepEvent.from_dict(data)

    def delete_event(self, event_id: str) -> None:
        api_client.delete(f"{self._prefix}/sitrep-events/{event_id}")

    def list_distributions(self, sitrep_id: str) -> list[dict]:
        return api_client.get(f"{self._prefix}/sitreps/{sitrep_id}/distributions") or []

    def create_distribution(self, sitrep_id: str, payload: dict) -> dict:
        return api_client.post(
            f"{self._prefix}/sitreps/{sitrep_id}/distributions",
            json=payload,
        )
