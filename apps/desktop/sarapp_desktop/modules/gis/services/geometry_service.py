from __future__ import annotations

import re
from dataclasses import replace

from modules.gis.models.feature_types import FeatureType
from modules.gis.models.spatial_feature import SpatialFeature
from modules.gis.models.geometry_types import GeometryType
from modules.gis.services.feature_registry import FeatureRegistry
from utils.coordinates import latlon_to_utm, utm_to_latlon

_WKT_HEAD_RE = re.compile(r"^\s*([A-Za-z]+)")

_METERS_PER_MILE = 1609.344


class GeometryBufferError(RuntimeError):
    """Raised when a buffer operation cannot be completed."""


class GeometryService:
    """Geometry helpers without requiring a GIS engine dependency."""

    def __init__(self, feature_registry: FeatureRegistry) -> None:
        self._feature_registry = feature_registry

    def validate_feature_geometry(self, feature_type: FeatureType, geometry_type: GeometryType) -> bool:
        return self._feature_registry.can_use_geometry(feature_type=feature_type, geometry_type=geometry_type)

    def parse_wkt_geometry_type(self, geometry_wkt: str | None) -> GeometryType | None:
        if not geometry_wkt:
            return None
        match = _WKT_HEAD_RE.match(geometry_wkt)
        if not match:
            return None
        token = match.group(1).upper().replace("MULTI", "")
        if token == "POINT":
            return GeometryType.POINT
        if token in {"LINESTRING", "LINEARRING"}:
            return GeometryType.LINE
        if token == "POLYGON":
            return GeometryType.POLYGON
        return None

    def normalize_geometry_wkt(self, geometry_wkt: str) -> str:
        """Normalize whitespace now; leave heavier transforms for future GIS adapter."""
        return " ".join(geometry_wkt.strip().split())

    def refresh_derived_fields(self, feature: SpatialFeature) -> SpatialFeature:
        """Placeholder for centroid/bounds recomputation when a GIS engine is configured."""
        normalized_wkt = self.normalize_geometry_wkt(feature.geometry_wkt)
        return replace(feature, geometry_wkt=normalized_wkt)

    def buffer_geometry_wkt(
        self,
        geometry_wkt: str,
        distance_meters: float,
        *,
        merge_overlaps: bool = False,
    ) -> str:
        """Buffer a lat/lon WKT geometry by `distance_meters` and return polygon WKT.

        Requires shapely (see requirements.txt). Distance math is done in a
        local UTM projection (zone derived from the geometry's first vertex)
        so the buffer distance is accurate in meters, then the result is
        reprojected back to WGS84 lat/lon for storage as WKT.
        """
        return buffer_wkt(geometry_wkt, distance_meters, merge_overlaps=merge_overlaps)


def _lazy_shapely():
    try:
        import shapely.geometry as shp_geom
        import shapely.ops as shp_ops
    except ImportError as exc:  # pragma: no cover - exercised only when shapely missing
        raise GeometryBufferError(
            "The 'shapely' package is required for buffer operations. "
            "Install it with `pip install shapely` (already listed in requirements.txt)."
        ) from exc
    return shp_geom, shp_ops


def wkt_coords(geometry_wkt: str) -> tuple[str, list[tuple[float, float]]]:
    """Very small WKT reader for POINT/LINESTRING/POLYGON (single ring, no holes)."""
    text = geometry_wkt.strip()
    match = _WKT_HEAD_RE.match(text)
    if not match:
        raise GeometryBufferError(f"Unrecognized WKT: {geometry_wkt!r}")
    kind = match.group(1).upper()
    body = text[match.end():].strip()
    body = body.strip("()")
    if kind == "POLYGON":
        # POLYGON((lon lat, lon lat, ...)) — strip one extra ring paren layer.
        body = body.strip("()")
    coords: list[tuple[float, float]] = []
    for pair in body.split(","):
        parts = pair.strip().split()
        if len(parts) < 2:
            continue
        lon, lat = float(parts[0]), float(parts[1])
        coords.append((lon, lat))
    return kind, coords


def buffer_wkt(geometry_wkt: str, distance_meters: float, *, merge_overlaps: bool = False) -> str:
    """Standalone buffer helper: lat/lon WKT (point/line/polygon) -> buffered polygon WKT."""
    if distance_meters <= 0:
        raise GeometryBufferError("Buffer distance must be positive.")

    shp_geom, _shp_ops = _lazy_shapely()
    kind, coords = wkt_coords(geometry_wkt)
    if not coords:
        raise GeometryBufferError("Geometry has no coordinates to buffer.")

    # Project to meters using the UTM zone of the first vertex.
    ref_lon, ref_lat = coords[0]
    utm_ref = latlon_to_utm(ref_lat, ref_lon)
    zone_number, zone_letter = utm_ref.zone_number, utm_ref.zone_letter

    projected = [latlon_to_utm(lat, lon) for lon, lat in coords]
    xy = [(p.easting, p.northing) for p in projected]

    if kind == "POINT":
        shape = shp_geom.Point(xy[0])
    elif kind in {"LINESTRING", "LINEARRING"}:
        shape = shp_geom.LineString(xy)
    elif kind == "POLYGON":
        shape = shp_geom.Polygon(xy)
    else:
        raise GeometryBufferError(f"Unsupported geometry kind for buffering: {kind}")

    buffered = shape.buffer(distance_meters, resolution=16)
    if buffered.is_empty:
        raise GeometryBufferError("Buffer produced an empty geometry.")

    if buffered.geom_type == "MultiPolygon" and merge_overlaps:
        from shapely.ops import unary_union

        buffered = unary_union(buffered)

    exterior_coords = list(buffered.exterior.coords) if buffered.geom_type == "Polygon" else list(
        max(buffered.geoms, key=lambda g: g.area).exterior.coords
    )

    lonlat_ring = [utm_to_latlon(zone_number, zone_letter, x, y) for x, y in exterior_coords]
    # utm_to_latlon returns (lat, lon); WKT wants "lon lat".
    ring_text = ", ".join(f"{lon:.7f} {lat:.7f}" for lat, lon in lonlat_ring)
    return f"POLYGON(({ring_text}))"


def buffer_distance_to_meters(distance: float, unit: str) -> float:
    unit = (unit or "meters").strip().lower()
    if unit in {"mi", "mile", "miles"}:
        return distance * _METERS_PER_MILE
    return distance
