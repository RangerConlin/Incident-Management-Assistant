from __future__ import annotations

from datetime import datetime, timezone

from modules.gis.models.spatial_feature_link import SpatialFeatureLink
from modules.gis.services.spatial_repository import SpatialRepository


class SpatialLinkService:
    """Helper service for module-level attach/detach spatial link operations."""

    def __init__(self, repository: SpatialRepository) -> None:
        self._repository = repository

    def attach_feature(
        self,
        feature_id: int,
        linked_module: str,
        linked_record_type: str,
        linked_record_id: str,
        relationship_type: str = "related",
    ) -> SpatialFeatureLink:
        return self._repository.create_link(
            SpatialFeatureLink(
                id=None,
                incident_id=self._repository.incident_id,
                feature_id=feature_id,
                linked_module=linked_module,
                linked_record_type=linked_record_type,
                linked_record_id=str(linked_record_id),
                relationship_type=relationship_type,
                created_at=datetime.now(timezone.utc),
            )
        )

    def detach_link(self, link_id: int) -> bool:
        return self._repository.delete_link(link_id)

    def list_features_for_record(self, module_name: str, record_type: str, record_id: str):
        owned = self._repository.list_features_for_record(module_name, record_type, str(record_id))
        related = self._repository.list_related_features(module_name, record_type, str(record_id))
        merged = {item.id: item for item in owned}
        for item in related:
            merged[item.id] = item
        return list(merged.values())
