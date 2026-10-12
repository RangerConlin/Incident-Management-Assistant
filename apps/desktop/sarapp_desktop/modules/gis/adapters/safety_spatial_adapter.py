from __future__ import annotations

from modules.gis.adapters._base_spatial_adapter import BaseSpatialAdapter, RecordRef
from modules.gis.models.feature_types import FeatureType


class SafetySpatialAdapter(BaseSpatialAdapter):
    """Adapter for safety-owned records such as hazards and closures."""

    def create_hazard_zone(self, hazard_id: str, label: str, geometry_wkt: str):
        return self.create_feature_for_record(
            RecordRef(module="safety", record_type="hazard", record_id=str(hazard_id)),
            FeatureType.HAZARD_ZONE,
            label,
            geometry_wkt,
        )
