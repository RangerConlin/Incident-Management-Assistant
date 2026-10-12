"""Shared SpatialFeature construction for map-window drawing tools."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from modules.gis.map_window.tools.draw_tools import line_to_wkt, polygon_to_wkt
from modules.gis.models.feature_types import FeatureType
from modules.gis.models.geometry_types import GeometryType
from modules.gis.models.spatial_feature import SpatialFeature
from modules.gis.services.feature_registry import FeatureRegistration

LonLat = tuple[float, float]


def geometry_wkt_for(geometry_type: GeometryType, lonlat: Sequence[LonLat]) -> str:
    """WKT for a drawn line or polygon; raises ValueError on too few vertices."""
    if geometry_type is GeometryType.LINE:
        return line_to_wkt(list(lonlat))
    if geometry_type is GeometryType.POLYGON:
        return polygon_to_wkt(list(lonlat))
    raise ValueError(f"Unsupported drawn geometry type: {geometry_type.value}")


def centroid_lonlat(geometry_type: GeometryType, lonlat: Sequence[LonLat]) -> LonLat:
    """Centroid of a line (length-weighted) or polygon (area-weighted).

    Planar math on lon/lat is adequate at incident scale; degenerate shapes
    fall back to the vertex average.
    """
    points = list(lonlat)
    fallback = (
        sum(p[0] for p in points) / len(points),
        sum(p[1] for p in points) / len(points),
    )
    if geometry_type is GeometryType.POLYGON:
        ring = points if points[0] == points[-1] else points + [points[0]]
        area2 = cx = cy = 0.0
        for (x0, y0), (x1, y1) in zip(ring, ring[1:]):
            cross = x0 * y1 - x1 * y0
            area2 += cross
            cx += (x0 + x1) * cross
            cy += (y0 + y1) * cross
        if abs(area2) < 1e-18:
            return fallback
        return cx / (3.0 * area2), cy / (3.0 * area2)
    if geometry_type is GeometryType.LINE:
        total = mx = my = 0.0
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
            total += length
            mx += (x0 + x1) / 2.0 * length
            my += (y0 + y1) / 2.0 * length
        if total < 1e-12:
            return fallback
        return mx / total, my / total
    return fallback


def build_drawn_feature(
    *,
    incident_id: str,
    registration: FeatureRegistration,
    geometry_type: GeometryType,
    lonlat: Sequence[LonLat],
    label: str,
    source_module: str,
    source_record_type: str,
    feature_subtype: str | None = None,
    is_planning_only: bool = False,
    layer_key: str | None = None,
    style_key: str | None = None,
    created_by: str | None = None,
) -> SpatialFeature:
    """Build an unsaved line/polygon SpatialFeature from (lon, lat) vertices."""
    wkt = geometry_wkt_for(geometry_type, lonlat)
    lons = [p[0] for p in lonlat]
    lats = [p[1] for p in lonlat]
    c_lon, c_lat = centroid_lonlat(geometry_type, lonlat)
    now = datetime.now(timezone.utc)
    return SpatialFeature(
        id=None,
        incident_id=incident_id,
        feature_type=registration.feature_type,
        feature_subtype=feature_subtype,
        geometry_type=geometry_type,
        label=label,
        description=None,
        status="active",
        source_module=source_module,
        source_record_type=source_record_type,
        source_record_id="",
        geometry_wkt=wkt,
        centroid_lat=c_lat,
        centroid_lon=c_lon,
        bbox_min_lat=min(lats),
        bbox_min_lon=min(lons),
        bbox_max_lat=max(lats),
        bbox_max_lon=max(lons),
        elevation_m=None,
        start_time=now,
        end_time=None,
        is_planning_only=is_planning_only,
        is_visible=True,
        is_locked=False,
        is_archived=False,
        layer_key=layer_key or registration.default_layer_key,
        style_key=style_key or registration.default_style_key,
        created_at=now,
        updated_at=now,
        created_by=created_by,
        updated_by=created_by,
    )
