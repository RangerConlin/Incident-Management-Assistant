"""Quick Add flows: Marker / Hazard / Clue / Task Area.

Each quick-add action arms a single-click "place at next map click" mode,
then creates a SpatialFeature through spatial_repository (never touching
Mongo directly, per agents.md).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable

from modules.gis.models.feature_types import FeatureType
from modules.gis.models.geometry_types import GeometryType
from modules.gis.models.spatial_feature import SpatialFeature
from modules.gis.services.feature_registry import FeatureRegistry
from modules.gis.services.spatial_repository import SpatialRepository
from utils.coordinates import latlon_to_utm, utm_to_latlon

logger = logging.getLogger(__name__)

_QUICK_TASK_AREA_HALF_WIDTH_M = 75.0

QUICK_ADD_KINDS: dict[str, FeatureType] = {
    "marker": FeatureType.PLANNING_SKETCH,
    "hazard": FeatureType.HAZARD_ZONE,
    "clue": FeatureType.CLUE,
    "task_area": FeatureType.TASK_AREA,
}


class QuickAddController:
    """Arms/disarms quick-add placement and creates the resulting feature."""

    def __init__(
        self,
        repository: SpatialRepository,
        feature_registry: FeatureRegistry,
        *,
        created_by: str | None = None,
    ) -> None:
        self._repository = repository
        self._feature_registry = feature_registry
        self._created_by = created_by
        self._armed_kind: str | None = None
        self._on_created: Callable[[SpatialFeature], None] | None = None

    @property
    def armed_kind(self) -> str | None:
        return self._armed_kind

    def arm(self, kind: str, on_created: Callable[[SpatialFeature], None] | None = None) -> None:
        if kind not in QUICK_ADD_KINDS:
            raise ValueError(f"Unknown quick-add kind: {kind}")
        self._armed_kind = kind
        self._on_created = on_created

    def disarm(self) -> None:
        self._armed_kind = None
        self._on_created = None

    def place_at(self, lat: float, lon: float, label: str | None = None) -> SpatialFeature | None:
        """Create the armed feature type at the given point, then disarm."""
        if self._armed_kind is None:
            return None
        feature_type = QUICK_ADD_KINDS[self._armed_kind]
        registration = self._feature_registry.get(feature_type)
        now = datetime.now(timezone.utc)

        if self._armed_kind == "task_area":
            geometry_type = GeometryType.POLYGON
            geometry_wkt, bounds = self._square_polygon_wkt(lat, lon, _QUICK_TASK_AREA_HALF_WIDTH_M)
        else:
            geometry_type = GeometryType.POINT
            geometry_wkt = f"POINT({lon:.7f} {lat:.7f})"
            bounds = (lat, lon, lat, lon)

        min_lat, min_lon, max_lat, max_lon = bounds
        feature = SpatialFeature(
            id=None,
            incident_id=self._repository.incident_id,
            feature_type=feature_type,
            feature_subtype=None,
            geometry_type=geometry_type,
            label=label or self._default_label(self._armed_kind),
            description=None,
            status="active",
            source_module="gis.map_window.quick_add",
            source_record_type="quick_add",
            source_record_id="",
            geometry_wkt=geometry_wkt,
            centroid_lat=lat,
            centroid_lon=lon,
            bbox_min_lat=min_lat,
            bbox_min_lon=min_lon,
            bbox_max_lat=max_lat,
            bbox_max_lon=max_lon,
            elevation_m=None,
            start_time=now,
            end_time=None,
            is_planning_only=False,
            is_visible=True,
            is_locked=False,
            is_archived=False,
            layer_key=registration.default_layer_key,
            style_key=registration.default_style_key,
            created_at=now,
            updated_at=now,
            created_by=self._created_by,
            updated_by=self._created_by,
        )
        try:
            created = self._repository.create_feature(feature)
        except Exception:
            logger.exception("Quick add create_feature failed for kind=%s", self._armed_kind)
            self.disarm()
            return None
        callback = self._on_created
        self.disarm()
        if callback is not None:
            callback(created)
        return created

    @staticmethod
    def _square_polygon_wkt(
        lat: float, lon: float, half_width_m: float
    ) -> tuple[str, tuple[float, float, float, float]]:
        utm = latlon_to_utm(lat, lon)
        corners_xy = [
            (utm.easting - half_width_m, utm.northing - half_width_m),
            (utm.easting + half_width_m, utm.northing - half_width_m),
            (utm.easting + half_width_m, utm.northing + half_width_m),
            (utm.easting - half_width_m, utm.northing + half_width_m),
        ]
        corners_latlon = [
            utm_to_latlon(utm.zone_number, utm.zone_letter, x, y) for x, y in corners_xy
        ]
        corners_latlon.append(corners_latlon[0])
        body = ", ".join(f"{c_lon:.7f} {c_lat:.7f}" for c_lat, c_lon in corners_latlon)
        lats = [c[0] for c in corners_latlon]
        lons = [c[1] for c in corners_latlon]
        bounds = (min(lats), min(lons), max(lats), max(lons))
        return f"POLYGON(({body}))", bounds

    @staticmethod
    def _default_label(kind: str) -> str:
        return {
            "marker": "Marker",
            "hazard": "Hazard",
            "clue": "Clue",
            "task_area": "Task Area",
        }.get(kind, kind.title())
