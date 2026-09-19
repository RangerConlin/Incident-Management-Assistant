"""State and feature construction for typed operational line/area drawing."""

from __future__ import annotations

from typing import Callable, Sequence

from modules.gis.map_window.operational_geometry_types import (
    OperationalGeometryType,
    operational_geometry_type,
)
from modules.gis.map_window.tools.feature_builder import build_drawn_feature
from modules.gis.models.geometry_types import GeometryType
from modules.gis.models.spatial_feature import SpatialFeature
from modules.gis.services.feature_registry import FeatureRegistry
from modules.gis.services.spatial_repository import SpatialRepository

_DRAW_TOOL_BY_GEOMETRY = {
    GeometryType.LINE: "draw_line",
    GeometryType.POLYGON: "draw_polygon",
}


class OperationalGeometryController:
    """Arms one typed line/area; the next finished drawing becomes that feature."""

    def __init__(self, repository: SpatialRepository, feature_registry: FeatureRegistry) -> None:
        self._repository = repository
        self._feature_registry = feature_registry
        self._armed_type: OperationalGeometryType | None = None
        self._on_created: Callable[[SpatialFeature], None] | None = None

    @property
    def armed_type(self) -> OperationalGeometryType | None:
        return self._armed_type

    @property
    def draw_tool_key(self) -> str | None:
        """The canvas draw tool that collects vertices for the armed type."""
        if self._armed_type is None:
            return None
        return _DRAW_TOOL_BY_GEOMETRY[self._armed_type.geometry_type]

    def arm(
        self,
        feature_type_value: str,
        geometry_type: GeometryType,
        *,
        subtype: str | None = None,
        on_created: Callable[[SpatialFeature], None] | None = None,
    ) -> OperationalGeometryType:
        definition = operational_geometry_type(feature_type_value, geometry_type, subtype)
        registration = self._feature_registry.get(definition.feature_type)
        if geometry_type not in registration.allowed_geometry_types:
            raise ValueError(f"{definition.feature_type.value} does not support {geometry_type.value} geometry")
        self._armed_type = definition
        self._on_created = on_created
        return definition

    def disarm(self) -> None:
        self._armed_type = None
        self._on_created = None

    def complete(self, lonlat: Sequence[tuple[float, float]]) -> SpatialFeature | None:
        """Persist the armed type from finished (lon, lat) vertices.

        Returns None when nothing is armed. Too few vertices raises
        ValueError and a failed save re-raises; both leave the type armed so
        the operator can draw again.
        """
        definition = self._armed_type
        if definition is None:
            return None
        registration = self._feature_registry.get(definition.feature_type)
        feature = build_drawn_feature(
            incident_id=self._repository.incident_id,
            registration=registration,
            geometry_type=definition.geometry_type,
            lonlat=lonlat,
            label=definition.display_name,
            feature_subtype=definition.subtype,
            style_key=definition.style_key,
            source_module="gis.map_window",
            source_record_type="operational_geometry",
        )
        created = self._repository.create_feature(feature)
        callback = self._on_created
        self.disarm()
        if callback is not None:
            callback(created)
        return created
