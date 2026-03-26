from __future__ import annotations

import re
from dataclasses import replace

from modules.gis.models.feature_types import FeatureType
from modules.gis.models.spatial_feature import SpatialFeature
from modules.gis.models.geometry_types import GeometryType
from modules.gis.services.feature_registry import FeatureRegistry

_WKT_HEAD_RE = re.compile(r"^\s*([A-Za-z]+)")


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
