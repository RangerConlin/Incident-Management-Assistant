from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from modules.gis.models.feature_types import FeatureType
from modules.gis.models.geometry_types import GeometryType
from modules.gis.models.spatial_feature import SpatialFeature
from modules.gis.services.feature_registry import FeatureRegistry
from modules.gis.services.geometry_service import GeometryService
from modules.gis.services.spatial_repository import SpatialRepository


@dataclass(frozen=True, slots=True)
class RecordRef:
    module: str
    record_type: str
    record_id: str


class BaseSpatialAdapter:
    """Base adapter that keeps module-owned records linked to shared geometry."""

    def __init__(
        self,
        repository: SpatialRepository,
        feature_registry: FeatureRegistry,
        geometry_service: GeometryService,
    ) -> None:
        self._repository = repository
        self._feature_registry = feature_registry
        self._geometry_service = geometry_service

    def create_feature_for_record(
        self,
        record_ref: RecordRef,
        feature_type: FeatureType,
        label: str,
        geometry_wkt: str,
        status: str = "active",
        description: str | None = None,
    ) -> SpatialFeature:
        registration = self._feature_registry.get(feature_type)
        geometry_type = self._geometry_service.parse_wkt_geometry_type(geometry_wkt)
        if geometry_type is None:
            raise ValueError("Unable to determine geometry type from WKT.")
        if geometry_type not in registration.allowed_geometry_types:
            raise ValueError(
                f"Feature type '{feature_type}' does not allow geometry type '{geometry_type}'."
            )

        normalized_wkt = self._geometry_service.normalize_geometry_wkt(geometry_wkt)
        now = datetime.now(timezone.utc)
        return self._repository.create_feature(
            SpatialFeature(
                id=None,
                incident_id=self._repository.incident_id,
                feature_type=feature_type,
                feature_subtype=None,
                geometry_type=GeometryType(geometry_type),
                label=label,
                description=description,
                status=status,
                source_module=record_ref.module,
                source_record_type=record_ref.record_type,
                source_record_id=str(record_ref.record_id),
                geometry_wkt=normalized_wkt,
                centroid_lat=None,
                centroid_lon=None,
                bbox_min_lat=None,
                bbox_min_lon=None,
                bbox_max_lat=None,
                bbox_max_lon=None,
                elevation_m=None,
                start_time=None,
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
        )

    def list_features_for_record(self, record_ref: RecordRef) -> list[SpatialFeature]:
        return self._repository.list_features_for_record(
            module_name=record_ref.module,
            record_type=record_ref.record_type,
            record_id=record_ref.record_id,
        )

    def update_feature_geometry(self, feature_id: int, geometry_wkt: str) -> SpatialFeature | None:
        geometry_type = self._geometry_service.parse_wkt_geometry_type(geometry_wkt)
        if geometry_type is None:
            raise ValueError("Unable to determine geometry type from WKT.")
        return self._repository.update_feature(
            feature_id,
            {
                "geometry_wkt": self._geometry_service.normalize_geometry_wkt(geometry_wkt),
                "geometry_type": geometry_type,
            },
        )
