"""Search Assignment Planner data model (SAR Toolkit).

Per docs/archive/design-documents/toolkit_sar_playbook.md, Operations owns
the official task/assignment record (IncidentCollections.TASKS). This model
represents only the SAR-specific augmentation, linked by `task_id` (the
Operations task's int_id) — never a second competing assignment/task id.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

SEARCH_METHODS = ["Parallel", "Grid", "Hasty", "Air-scent", "Sector", "Line"]


@dataclass(slots=True)
class SearchTaskDetail:
    id: str = ""
    incident_id: str = ""
    task_id: Optional[int] = None
    segment_id: Optional[str] = None
    search_method: str = "Parallel"
    track_spacing: str = ""
    completion_criteria: str = ""
    safety_notes: str = ""
    radio_channel: str = ""
    team_leader: str = ""
    departure_time: Optional[str] = None
    due_back_time: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SearchTaskDetail":
        return cls(
            id=str(d.get("id") or ""),
            incident_id=str(d.get("incident_id") or ""),
            task_id=d.get("task_id"),
            segment_id=d.get("segment_id"),
            search_method=str(d.get("search_method") or "Parallel"),
            track_spacing=str(d.get("track_spacing") or ""),
            completion_criteria=str(d.get("completion_criteria") or ""),
            safety_notes=str(d.get("safety_notes") or ""),
            radio_channel=str(d.get("radio_channel") or ""),
            team_leader=str(d.get("team_leader") or ""),
            departure_time=d.get("departure_time"),
            due_back_time=d.get("due_back_time"),
            created_at=str(d.get("created_at") or ""),
            updated_at=str(d.get("updated_at") or ""),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "segment_id": self.segment_id or None,
            "search_method": self.search_method,
            "track_spacing": self.track_spacing,
            "completion_criteria": self.completion_criteria,
            "safety_notes": self.safety_notes,
            "radio_channel": self.radio_channel,
            "team_leader": self.team_leader,
            "departure_time": self.departure_time or None,
            "due_back_time": self.due_back_time or None,
        }
