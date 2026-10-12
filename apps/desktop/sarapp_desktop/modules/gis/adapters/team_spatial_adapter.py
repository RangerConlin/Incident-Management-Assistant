from __future__ import annotations

from modules.gis.adapters._base_spatial_adapter import BaseSpatialAdapter, RecordRef
from modules.gis.models.feature_types import FeatureType


class TeamSpatialAdapter(BaseSpatialAdapter):
    """Adapter for operations team records."""

    def create_team_location(self, team_id: str, label: str, geometry_wkt: str):
        return self.create_feature_for_record(
            RecordRef(module="operations", record_type="team", record_id=str(team_id)),
            FeatureType.TEAM_LOCATION,
            label,
            geometry_wkt,
        )

    def create_team_track(self, team_id: str, label: str, geometry_wkt: str):
        return self.create_feature_for_record(
            RecordRef(module="operations", record_type="team", record_id=str(team_id)),
            FeatureType.TEAM_TRACK,
            label,
            geometry_wkt,
        )
