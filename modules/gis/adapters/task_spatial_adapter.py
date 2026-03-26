from __future__ import annotations

from modules.gis.adapters._base_spatial_adapter import BaseSpatialAdapter, RecordRef
from modules.gis.models.feature_types import FeatureType


class TaskSpatialAdapter(BaseSpatialAdapter):
    """Adapter for operations/planning task records."""

    def create_task_point(self, task_id: str, label: str, geometry_wkt: str):
        return self.create_feature_for_record(
            RecordRef(module="operations", record_type="task", record_id=str(task_id)),
            FeatureType.TASK_POINT,
            label,
            geometry_wkt,
        )

    def create_task_route(self, task_id: str, label: str, geometry_wkt: str):
        return self.create_feature_for_record(
            RecordRef(module="operations", record_type="task", record_id=str(task_id)),
            FeatureType.TASK_ROUTE,
            label,
            geometry_wkt,
        )
