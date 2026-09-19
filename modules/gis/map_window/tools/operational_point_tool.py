"""State and feature construction for typed operational-point placement."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from modules.gis.map_window.operational_point_types import (
    OperationalPointType,
    operational_point_type,
)
from modules.gis.models.geometry_types import GeometryType
from modules.gis.models.spatial_feature import SpatialFeature
from modules.gis.services.feature_registry import FeatureRegistry
from modules.gis.services.spatial_repository import SpatialRepository


class OperationalPointController:
    """Arms one typed point and persists it on the next map click."""

    def __init__(self, repository: SpatialRepository, feature_registry: FeatureRegistry) -> None:
        self._repository = repository
        self._feature_registry = feature_registry
        self._armed_type: OperationalPointType | None = None
        self._on_created: Callable[[SpatialFeature], None] | None = None

    @property
    def armed_type(self) -> OperationalPointType | None:
        return self._armed_type

    def arm(
        self,
        feature_type_value: str,
        *,
        on_created: Callable[[SpatialFeature], None] | None = None,
    ) -> OperationalPointType:
        definition = operational_point_type(feature_type_value)
        registration = self._feature_registry.get(definition.feature_type)
        if GeometryType.POINT not in registration.allowed_geometry_types:
            raise ValueError(f"{definition.feature_type.value} does not support point geometry")
        self._armed_type = definition
        self._on_created = on_created
        return definition

    def disarm(self) -> None:
        self._armed_type = None
        self._on_created = None

    def place_at(self, lat: float, lon: float) -> SpatialFeature | None:
        definition = self._armed_type
        if definition is None:
            return None
        registration = self._feature_registry.get(definition.feature_type)
        now = datetime.now(timezone.utc)
        feature = SpatialFeature(
            id=None,
            incident_id=self._repository.incident_id,
            feature_type=definition.feature_type,
            feature_subtype=None,
            geometry_type=GeometryType.POINT,
            label=definition.display_name,
            description=None,
            status="active",
            source_module="gis.map_window",
            source_record_type="operational_point",
            source_record_id="",
            geometry_wkt=f"POINT({lon:.7f} {lat:.7f})",
            centroid_lat=lat,
            centroid_lon=lon,
            bbox_min_lat=lat,
            bbox_min_lon=lon,
            bbox_max_lat=lat,
            bbox_max_lon=lon,
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
            created_by=None,
            updated_by=None,
        )
        created = self._repository.create_feature(feature)
        callback = self._on_created
        self.disarm()
        if callback is not None:
            callback(created)
        return created
