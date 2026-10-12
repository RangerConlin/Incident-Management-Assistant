from __future__ import annotations

from modules.gis.adapters._base_spatial_adapter import BaseSpatialAdapter, RecordRef
from modules.gis.models.feature_types import FeatureType


class CommsSpatialAdapter(BaseSpatialAdapter):
    """Adapter for communications-owned records."""

    def create_repeater_site(self, site_id: str, label: str, geometry_wkt: str):
        return self.create_feature_for_record(
            RecordRef(module="communications", record_type="site", record_id=str(site_id)),
            FeatureType.REPEATER_SITE,
            label,
            geometry_wkt,
        )
