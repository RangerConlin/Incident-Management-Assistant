from __future__ import annotations

from modules.gis.adapters._base_spatial_adapter import BaseSpatialAdapter, RecordRef
from modules.gis.models.feature_types import FeatureType


class IntelSpatialAdapter(BaseSpatialAdapter):
    """Adapter for intel-owned records such as clues and subject events."""

    def create_clue_feature(self, clue_id: str, label: str, geometry_wkt: str):
        return self.create_feature_for_record(
            RecordRef(module="intel", record_type="clue", record_id=str(clue_id)),
            FeatureType.CLUE,
            label,
            geometry_wkt,
        )

    def create_subject_event(self, subject_id: str, label: str, geometry_wkt: str):
        return self.create_feature_for_record(
            RecordRef(module="intel", record_type="subject", record_id=str(subject_id)),
            FeatureType.SUBJECT_EVENT_LOCATION,
            label,
            geometry_wkt,
        )
