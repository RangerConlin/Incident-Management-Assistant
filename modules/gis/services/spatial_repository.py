from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from utils.api_client import api_client
from utils import incident_context
from modules.gis.models.feature_types import FeatureType
from modules.gis.models.geometry_types import GeometryType
from modules.gis.models.spatial_feature import SpatialFeature
from modules.gis.models.spatial_feature_link import SpatialFeatureLink


class SpatialRepository:
    """Incident-scoped persistence for shared spatial features and links."""

    def __init__(self, incident_id: str | None = None) -> None:
        self._incident_id = incident_id or incident_context.get_active_incident_id()
        if not self._incident_id:
            raise RuntimeError("An active incident is required for the spatial repository.")

    @property
    def incident_id(self) -> str:
        return str(self._incident_id)

    def create_feature(self, feature: SpatialFeature) -> SpatialFeature:
        body = _feature_to_dict(feature)
        doc = api_client.post(f"/api/incidents/{self.incident_id}/gis/features", json=body)
        return _doc_to_feature(doc)

    def update_feature(self, feature_id: int, updates: dict[str, Any]) -> SpatialFeature | None:
        if not updates:
            return self.get_feature(feature_id)
        for flag in ("is_planning_only", "is_visible", "is_locked", "is_archived"):
            if flag in updates:
                updates[flag] = bool(updates[flag])
        for time_field in ("start_time", "end_time"):
            if time_field in updates and isinstance(updates[time_field], datetime):
                updates[time_field] = _as_iso(updates[time_field])
        try:
            doc = api_client.patch(
                f"/api/incidents/{self.incident_id}/gis/features/{feature_id}",
                json=updates,
            )
            return _doc_to_feature(doc)
        except Exception:
            return None

    def archive_feature(self, feature_id: int, updated_by: str | None = None) -> SpatialFeature | None:
        try:
            doc = api_client.patch(
                f"/api/incidents/{self.incident_id}/gis/features/{feature_id}/archive",
                json={"updated_by": updated_by},
            )
            return _doc_to_feature(doc)
        except Exception:
            return None

    def get_feature(self, feature_id: int) -> SpatialFeature | None:
        try:
            doc = api_client.get(f"/api/incidents/{self.incident_id}/gis/features/{feature_id}")
            return _doc_to_feature(doc)
        except Exception:
            return None

    def list_features(self, include_archived: bool = False) -> list[SpatialFeature]:
        try:
            docs = api_client.get(
                f"/api/incidents/{self.incident_id}/gis/features",
                params={"include_archived": include_archived},
            ) or []
            return [_doc_to_feature(d) for d in docs]
        except Exception:
            return []

    def list_features_by_type(self, feature_type: FeatureType, include_archived: bool = False) -> list[SpatialFeature]:
        try:
            docs = api_client.get(
                f"/api/incidents/{self.incident_id}/gis/features/by-type/{feature_type}",
                params={"include_archived": include_archived},
            ) or []
            return [_doc_to_feature(d) for d in docs]
        except Exception:
            return []

    def list_features_by_module(self, module_name: str, include_archived: bool = False) -> list[SpatialFeature]:
        try:
            docs = api_client.get(
                f"/api/incidents/{self.incident_id}/gis/features/by-module/{module_name}",
                params={"include_archived": include_archived},
            ) or []
            return [_doc_to_feature(d) for d in docs]
        except Exception:
            return []

    def list_features_for_record(self, module_name: str, record_type: str, record_id: str) -> list[SpatialFeature]:
        try:
            docs = api_client.get(
                f"/api/incidents/{self.incident_id}/gis/features/for-record",
                params={"module_name": module_name, "record_type": record_type, "record_id": record_id},
            ) or []
            return [_doc_to_feature(d) for d in docs]
        except Exception:
            return []

    def create_link(self, link: SpatialFeatureLink) -> SpatialFeatureLink:
        body = {
            "feature_id": link.feature_id,
            "linked_module": link.linked_module,
            "linked_record_type": link.linked_record_type,
            "linked_record_id": link.linked_record_id,
            "relationship_type": link.relationship_type,
        }
        doc = api_client.post(f"/api/incidents/{self.incident_id}/gis/links", json=body)
        return _doc_to_link(doc)

    def list_links_for_feature(self, feature_id: int) -> list[SpatialFeatureLink]:
        try:
            docs = api_client.get(
                f"/api/incidents/{self.incident_id}/gis/features/{feature_id}/links",
            ) or []
            return [_doc_to_link(d) for d in docs]
        except Exception:
            return []

    def list_related_features(self, module_name: str, record_type: str, record_id: str) -> list[SpatialFeature]:
        try:
            docs = api_client.get(
                f"/api/incidents/{self.incident_id}/gis/related-features",
                params={"module_name": module_name, "record_type": record_type, "record_id": record_id},
            ) or []
            return [_doc_to_feature(d) for d in docs]
        except Exception:
            return []

    def delete_link(self, link_id: int) -> bool:
        try:
            api_client.delete(f"/api/incidents/{self.incident_id}/gis/links/{link_id}")
            return True
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _as_iso(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.astimezone(timezone.utc).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _feature_to_dict(feature: SpatialFeature) -> dict:
    return {
        "feature_type": str(feature.feature_type),
        "feature_subtype": feature.feature_subtype,
        "geometry_type": str(feature.geometry_type),
        "label": feature.label,
        "description": feature.description,
        "status": feature.status,
        "source_module": feature.source_module,
        "source_record_type": feature.source_record_type,
        "source_record_id": feature.source_record_id,
        "geometry_wkt": feature.geometry_wkt,
        "centroid_lat": feature.centroid_lat,
        "centroid_lon": feature.centroid_lon,
        "bbox_min_lat": feature.bbox_min_lat,
        "bbox_min_lon": feature.bbox_min_lon,
        "bbox_max_lat": feature.bbox_max_lat,
        "bbox_max_lon": feature.bbox_max_lon,
        "elevation_m": feature.elevation_m,
        "start_time": _as_iso(feature.start_time),
        "end_time": _as_iso(feature.end_time),
        "is_planning_only": feature.is_planning_only,
        "is_visible": feature.is_visible,
        "is_locked": feature.is_locked,
        "is_archived": feature.is_archived,
        "layer_key": feature.layer_key,
        "style_key": feature.style_key,
        "created_at": _as_iso(feature.created_at),
        "updated_at": _as_iso(feature.updated_at),
        "created_by": feature.created_by,
        "updated_by": feature.updated_by,
    }


def _doc_to_feature(doc: dict) -> SpatialFeature:
    return SpatialFeature(
        id=doc.get("id"),
        incident_id=str(doc.get("incident_id", "")),
        feature_type=FeatureType(str(doc.get("feature_type", ""))),
        feature_subtype=doc.get("feature_subtype"),
        geometry_type=GeometryType(str(doc.get("geometry_type", ""))),
        label=str(doc.get("label", "")),
        description=doc.get("description"),
        status=str(doc.get("status", "active")),
        source_module=str(doc.get("source_module", "")),
        source_record_type=str(doc.get("source_record_type", "")),
        source_record_id=str(doc.get("source_record_id", "")),
        geometry_wkt=str(doc.get("geometry_wkt", "")),
        centroid_lat=doc.get("centroid_lat"),
        centroid_lon=doc.get("centroid_lon"),
        bbox_min_lat=doc.get("bbox_min_lat"),
        bbox_min_lon=doc.get("bbox_min_lon"),
        bbox_max_lat=doc.get("bbox_max_lat"),
        bbox_max_lon=doc.get("bbox_max_lon"),
        elevation_m=doc.get("elevation_m"),
        start_time=_parse_iso(doc.get("start_time")),
        end_time=_parse_iso(doc.get("end_time")),
        is_planning_only=bool(doc.get("is_planning_only", False)),
        is_visible=bool(doc.get("is_visible", True)),
        is_locked=bool(doc.get("is_locked", False)),
        is_archived=bool(doc.get("is_archived", False)),
        layer_key=str(doc.get("layer_key", "")),
        style_key=doc.get("style_key"),
        created_at=_parse_iso(doc.get("created_at")),
        updated_at=_parse_iso(doc.get("updated_at")),
        created_by=doc.get("created_by"),
        updated_by=doc.get("updated_by"),
    )


def _doc_to_link(doc: dict) -> SpatialFeatureLink:
    return SpatialFeatureLink(
        id=doc.get("id"),
        incident_id=str(doc.get("incident_id", "")),
        feature_id=int(doc.get("feature_id", 0)),
        linked_module=str(doc.get("linked_module", "")),
        linked_record_type=str(doc.get("linked_record_type", "")),
        linked_record_id=str(doc.get("linked_record_id", "")),
        relationship_type=str(doc.get("relationship_type", "")),
        created_at=_parse_iso(doc.get("created_at")),
    )
