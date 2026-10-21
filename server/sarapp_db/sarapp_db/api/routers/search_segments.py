"""Search Segment Management router (SAR Toolkit) — MongoDB-backed.

Owns the canonical SAR search segment list per
docs/archive/design-documents/toolkit_sar_playbook.md ("Search Segment
Management"). A segment does NOT require GIS geometry — `gis_reference` is
always optional so a segment can be created from a paper map, verbal
boundary, grid reference, or landmark description alone. Full GIS authoring
stays owned by the GIS module (IncidentCollections.SPATIAL_FEATURES); this
router only stores a plain, non-authoritative `gis_reference` value (and,
for auto-generated grids, simple computed rectangle corners — see
`_rectangle_corners` below) as a placeholder until real GIS integration
exists.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()

PLANNING_STATUSES = ["draft", "ready for evaluation", "evaluated", "ready for assignment", "deferred"]
SEARCH_STATUSES = ["unassigned", "assigned", "in progress", "searched", "partially searched"]
REVIEW_STATUSES = ["pending review", "needs re-search", "closed"]

# Acres per square meter, used to convert a cell size in acres into a side
# length in meters for the rectangle-tiling math below.
_SQ_METERS_PER_ACRE = 4046.8564224
_EARTH_RADIUS_M = 6371000.0


class SearchSegmentsRepository(BaseRepository):
    collection_name = IncidentCollections.SEARCH_SEGMENTS


def _repo(incident_id: str) -> SearchSegmentsRepository:
    return SearchSegmentsRepository(get_incident_db(incident_id))


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SegmentPayload(BaseModel):
    name: str
    description: str = ""
    boundary_description: str = ""
    map_reference: str = ""
    gis_reference: Optional[str] = None
    parent_segment_id: Optional[str] = None
    terrain_notes: str = ""
    access_notes: str = ""
    hazards: str = ""
    size_estimate: Optional[float] = None
    planning_status: str = "draft"
    search_status: str = "unassigned"
    review_status: str = "pending review"
    created_by: str = ""


def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "segment_id": str(doc.get("_id") or ""),
        "incident_id": str(doc.get("incident_id") or ""),
        "name": str(doc.get("name") or ""),
        "description": str(doc.get("description") or ""),
        "boundary_description": str(doc.get("boundary_description") or ""),
        "map_reference": str(doc.get("map_reference") or ""),
        "gis_reference": doc.get("gis_reference"),
        "parent_segment_id": doc.get("parent_segment_id"),
        "terrain_notes": str(doc.get("terrain_notes") or ""),
        "access_notes": str(doc.get("access_notes") or ""),
        "hazards": str(doc.get("hazards") or ""),
        "size_estimate": doc.get("size_estimate"),
        "planning_status": str(doc.get("planning_status") or "draft"),
        "search_status": str(doc.get("search_status") or "unassigned"),
        "review_status": str(doc.get("review_status") or "pending review"),
        "created_by": str(doc.get("created_by") or ""),
        "created_at": str(doc.get("created_at") or ""),
        "updated_at": str(doc.get("updated_at") or ""),
    }


@router.get("/incidents/{incident_id}/search-segments")
def list_segments(incident_id: str) -> List[Dict[str, Any]]:
    repo = _repo(incident_id)
    rows = repo.find_many({"incident_id": incident_id}, sort=[("name", 1)])
    return [_serialize(r) for r in rows]


@router.get("/incidents/{incident_id}/search-segments/{segment_id}")
def get_segment(incident_id: str, segment_id: str) -> Dict[str, Any]:
    repo = _repo(incident_id)
    doc = repo.find_by_id(segment_id)
    if not doc or str(doc.get("incident_id")) != incident_id:
        raise HTTPException(status_code=404, detail="Search segment not found")
    return _serialize(doc)


@router.post("/incidents/{incident_id}/search-segments", status_code=201)
def create_segment(incident_id: str, payload: SegmentPayload) -> Dict[str, Any]:
    _validate_statuses(payload)
    values = payload.model_dump()
    doc = _repo(incident_id).insert_one({"incident_id": incident_id, **values})
    return _serialize(doc)


@router.put("/incidents/{incident_id}/search-segments/{segment_id}")
def update_segment(incident_id: str, segment_id: str, payload: SegmentPayload) -> Dict[str, Any]:
    _validate_statuses(payload)
    repo = _repo(incident_id)
    existing = repo.find_by_id(segment_id)
    if not existing or str(existing.get("incident_id")) != incident_id:
        raise HTTPException(status_code=404, detail="Search segment not found")
    repo.update_one(segment_id, {"incident_id": incident_id, **payload.model_dump()})
    updated = repo.find_by_id(segment_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Search segment not found after update")
    return _serialize(updated)


@router.delete("/incidents/{incident_id}/search-segments/{segment_id}")
def delete_segment(incident_id: str, segment_id: str) -> Dict[str, bool]:
    repo = _repo(incident_id)
    existing = repo.find_by_id(segment_id)
    if not existing or str(existing.get("incident_id")) != incident_id:
        raise HTTPException(status_code=404, detail="Search segment not found")
    return {"ok": repo.soft_delete(segment_id)}


def _validate_statuses(payload: SegmentPayload) -> None:
    if payload.planning_status not in PLANNING_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid planning_status: {payload.planning_status}")
    if payload.search_status not in SEARCH_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid search_status: {payload.search_status}")
    if payload.review_status not in REVIEW_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid review_status: {payload.review_status}")


# ---------------------------------------------------------------------------
# Auto-Create Grid
# ---------------------------------------------------------------------------


class GridRequest(BaseModel):
    origin_lat: float
    origin_lon: float
    orientation_deg: float = 0.0
    cell_acres: float = 40.0
    rows: int = 1
    columns: int = 1
    naming_scheme: str = "sequential"  # "sequential" (SEG-01..) or "row_col" (A1, A2..)
    name_prefix: str = "SEG"
    # Stored as a plain value only — real polygon clipping against another
    # feature (e.g. an incident boundary) is NOT implemented here. GIS
    # ownership of actual clipping stays with the GIS module; see module
    # docstring and docs/archive/design-documents/toolkit_sar_playbook.md.
    clip_to: Optional[str] = None
    created_by: str = ""


def _destination_point(lat: float, lon: float, bearing_deg: float, distance_m: float) -> tuple[float, float]:
    """Great-circle destination point given a start point, bearing, and distance."""
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    brng = math.radians(bearing_deg)
    d_r = distance_m / _EARTH_RADIUS_M

    lat2 = math.asin(
        math.sin(lat1) * math.cos(d_r) + math.cos(lat1) * math.sin(d_r) * math.cos(brng)
    )
    lon2 = lon1 + math.atan2(
        math.sin(brng) * math.sin(d_r) * math.cos(lat1),
        math.cos(d_r) - math.sin(lat1) * math.sin(lat2),
    )
    return math.degrees(lat2), math.degrees(lon2)


def _rectangle_corners(
    origin_lat: float,
    origin_lon: float,
    orientation_deg: float,
    row_idx: int,
    col_idx: int,
    cell_side_m: float,
) -> List[Dict[str, float]]:
    """Compute the four corner lat/lons of one grid cell.

    The grid's local axes are rotated `orientation_deg` clockwise from true
    north; `row_idx`/`col_idx` are 0-based offsets of this cell from the
    origin along those axes. This is plain rectangle tiling with rotation
    around an origin — not a GIS feature; see module docstring.
    """
    along_bearing = orientation_deg
    across_bearing = (orientation_deg + 90.0) % 360.0

    def offset_point(d_along: float, d_across: float) -> tuple[float, float]:
        lat1, lon1 = _destination_point(origin_lat, origin_lon, along_bearing, d_along)
        return _destination_point(lat1, lon1, across_bearing, d_across)

    near_along = row_idx * cell_side_m
    far_along = (row_idx + 1) * cell_side_m
    near_across = col_idx * cell_side_m
    far_across = (col_idx + 1) * cell_side_m

    corners = [
        offset_point(near_along, near_across),
        offset_point(near_along, far_across),
        offset_point(far_along, far_across),
        offset_point(far_along, near_across),
    ]
    return [{"lat": lat, "lon": lon} for lat, lon in corners]


def _grid_name(scheme: str, prefix: str, row_idx: int, col_idx: int, seq: int) -> str:
    if scheme == "row_col":
        # A1, A2, ... row letters, 1-based column numbers
        row_letter = chr(ord("A") + row_idx) if row_idx < 26 else f"R{row_idx + 1}"
        return f"{row_letter}{col_idx + 1}"
    return f"{prefix}-{seq:02d}"


@router.post("/incidents/{incident_id}/search-segments/auto-create-grid", status_code=201)
def auto_create_grid(incident_id: str, request: GridRequest) -> List[Dict[str, Any]]:
    if request.rows < 1 or request.columns < 1:
        raise HTTPException(status_code=422, detail="rows and columns must each be at least 1")
    if request.cell_acres <= 0:
        raise HTTPException(status_code=422, detail="cell_acres must be positive")

    cell_side_m = math.sqrt(request.cell_acres * _SQ_METERS_PER_ACRE)
    repo = _repo(incident_id)
    batch_id = str(uuid.uuid4())

    documents: List[Dict[str, Any]] = []
    seq = 0
    for row_idx in range(request.rows):
        for col_idx in range(request.columns):
            seq += 1
            corners = _rectangle_corners(
                request.origin_lat,
                request.origin_lon,
                request.orientation_deg,
                row_idx,
                col_idx,
                cell_side_m,
            )
            name = _grid_name(request.naming_scheme, request.name_prefix, row_idx, col_idx, seq)
            gis_reference = {
                "kind": "auto_grid_rectangle_placeholder",
                "corners": corners,
                "row": row_idx,
                "column": col_idx,
                "clip_to": request.clip_to,
                "note": (
                    "Computed rectangle corners only — not a validated GIS "
                    "feature. Real clipping/geometry ownership stays with "
                    "the GIS module."
                ),
            }
            documents.append(
                {
                    "incident_id": incident_id,
                    "grid_batch_id": batch_id,
                    "name": name,
                    "description": "",
                    "boundary_description": "",
                    "map_reference": "",
                    "gis_reference": gis_reference,
                    "parent_segment_id": None,
                    "terrain_notes": "",
                    "access_notes": "",
                    "hazards": "",
                    "size_estimate": request.cell_acres,
                    "planning_status": "draft",
                    "search_status": "unassigned",
                    "review_status": "pending review",
                    "created_by": request.created_by,
                }
            )

    repo.bulk_insert(documents)
    rows = repo.find_many({"incident_id": incident_id, "grid_batch_id": batch_id})
    return [_serialize(r) for r in rows]
