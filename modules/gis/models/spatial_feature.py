from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .feature_types import FeatureType
from .geometry_types import GeometryType


@dataclass(slots=True)
class SpatialFeature:
    id: int | None
    incident_id: str
    feature_type: FeatureType
    feature_subtype: str | None
    geometry_type: GeometryType
    label: str
    description: str | None
    status: str
    source_module: str
    source_record_type: str
    source_record_id: str
    geometry_wkt: str
    centroid_lat: float | None
    centroid_lon: float | None
    bbox_min_lat: float | None
    bbox_min_lon: float | None
    bbox_max_lat: float | None
    bbox_max_lon: float | None
    elevation_m: float | None
    start_time: datetime | None
    end_time: datetime | None
    is_planning_only: bool
    is_visible: bool
    is_locked: bool
    is_archived: bool
    layer_key: str
    style_key: str | None
    created_at: datetime | None
    updated_at: datetime | None
    created_by: str | None
    updated_by: str | None
