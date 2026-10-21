"""Search segment data model (SAR Toolkit — Search Segment Management).

Fields mirror docs/archive/design-documents/toolkit_sar_playbook.md's
"Suggested segment fields" exactly. A segment never requires GIS geometry —
`gis_reference` is always optional.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

PLANNING_STATUSES = ["draft", "ready for evaluation", "evaluated", "ready for assignment", "deferred"]
SEARCH_STATUSES = ["unassigned", "assigned", "in progress", "searched", "partially searched"]
REVIEW_STATUSES = ["pending review", "needs re-search", "closed"]


@dataclass(slots=True)
class SearchSegment:
    segment_id: str = ""
    incident_id: str = ""
    name: str = ""
    description: str = ""
    boundary_description: str = ""
    map_reference: str = ""
    gis_reference: Optional[Any] = None
    parent_segment_id: Optional[str] = None
    terrain_notes: str = ""
    access_notes: str = ""
    hazards: str = ""
    size_estimate: Optional[float] = None
    planning_status: str = "draft"
    search_status: str = "unassigned"
    review_status: str = "pending review"
    created_by: str = ""
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SearchSegment":
        return cls(
            segment_id=str(d.get("segment_id") or ""),
            incident_id=str(d.get("incident_id") or ""),
            name=str(d.get("name") or ""),
            description=str(d.get("description") or ""),
            boundary_description=str(d.get("boundary_description") or ""),
            map_reference=str(d.get("map_reference") or ""),
            gis_reference=d.get("gis_reference"),
            parent_segment_id=d.get("parent_segment_id"),
            terrain_notes=str(d.get("terrain_notes") or ""),
            access_notes=str(d.get("access_notes") or ""),
            hazards=str(d.get("hazards") or ""),
            size_estimate=d.get("size_estimate"),
            planning_status=str(d.get("planning_status") or "draft"),
            search_status=str(d.get("search_status") or "unassigned"),
            review_status=str(d.get("review_status") or "pending review"),
            created_by=str(d.get("created_by") or ""),
            created_at=str(d.get("created_at") or ""),
            updated_at=str(d.get("updated_at") or ""),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "boundary_description": self.boundary_description,
            "map_reference": self.map_reference,
            "gis_reference": self.gis_reference,
            "parent_segment_id": self.parent_segment_id or None,
            "terrain_notes": self.terrain_notes,
            "access_notes": self.access_notes,
            "hazards": self.hazards,
            "size_estimate": self.size_estimate,
            "planning_status": self.planning_status,
            "search_status": self.search_status,
            "review_status": self.review_status,
            "created_by": self.created_by,
        }
