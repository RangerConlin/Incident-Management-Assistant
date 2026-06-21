"""GIS spatial features router — per-incident."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException

from sarapp_db.mongo.db_manager import DatabaseManager
from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.int_id import _ensure_int_ids, next_int_id

router = APIRouter()

FEATURES_COL = IncidentCollections.SPATIAL_FEATURES
LINKS_COL = IncidentCollections.SPATIAL_FEATURE_LINKS


def _features(incident_id: str):
    return DatabaseManager().get_incident_db(incident_id)[FEATURES_COL]


def _links(incident_id: str):
    return DatabaseManager().get_incident_db(incident_id)[LINKS_COL]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _feature_out(doc: dict) -> dict:
    return {
        "id": doc.get("int_id"),
        "incident_id": doc.get("incident_id", ""),
        "feature_type": doc.get("feature_type", ""),
        "feature_subtype": doc.get("feature_subtype"),
        "geometry_type": doc.get("geometry_type", ""),
        "label": doc.get("label", ""),
        "description": doc.get("description"),
        "status": doc.get("status", "active"),
        "source_module": doc.get("source_module", ""),
        "source_record_type": doc.get("source_record_type", ""),
        "source_record_id": doc.get("source_record_id", ""),
        "geometry_wkt": doc.get("geometry_wkt", ""),
        "centroid_lat": doc.get("centroid_lat"),
        "centroid_lon": doc.get("centroid_lon"),
        "bbox_min_lat": doc.get("bbox_min_lat"),
        "bbox_min_lon": doc.get("bbox_min_lon"),
        "bbox_max_lat": doc.get("bbox_max_lat"),
        "bbox_max_lon": doc.get("bbox_max_lon"),
        "elevation_m": doc.get("elevation_m"),
        "start_time": doc.get("start_time"),
        "end_time": doc.get("end_time"),
        "is_planning_only": bool(doc.get("is_planning_only", False)),
        "is_visible": bool(doc.get("is_visible", True)),
        "is_locked": bool(doc.get("is_locked", False)),
        "is_archived": bool(doc.get("is_archived", False)),
        "layer_key": doc.get("layer_key", ""),
        "style_key": doc.get("style_key"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
        "created_by": doc.get("created_by"),
        "updated_by": doc.get("updated_by"),
    }


def _link_out(doc: dict) -> dict:
    return {
        "id": doc.get("int_id"),
        "incident_id": doc.get("incident_id", ""),
        "feature_id": doc.get("feature_id"),
        "linked_module": doc.get("linked_module", ""),
        "linked_record_type": doc.get("linked_record_type", ""),
        "linked_record_id": doc.get("linked_record_id", ""),
        "relationship_type": doc.get("relationship_type", ""),
        "created_at": doc.get("created_at"),
    }


# -------------------------------------------------------------------------
# Features
# -------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/gis/features")
def list_features(incident_id: str, include_archived: bool = False) -> List[Dict[str, Any]]:
    col = _features(incident_id)
    _ensure_int_ids(col)
    q: Dict[str, Any] = {"incident_id": incident_id, "deleted": {"$ne": True}}
    if not include_archived:
        q["is_archived"] = {"$ne": True}
    docs = list(col.find(q, sort=[("created_at", 1)]))
    return [_feature_out(d) for d in docs]


@router.get("/incidents/{incident_id}/gis/features/by-type/{feature_type}")
def list_features_by_type(incident_id: str, feature_type: str, include_archived: bool = False) -> List[Dict[str, Any]]:
    col = _features(incident_id)
    _ensure_int_ids(col)
    q: Dict[str, Any] = {"incident_id": incident_id, "feature_type": feature_type, "deleted": {"$ne": True}}
    if not include_archived:
        q["is_archived"] = {"$ne": True}
    docs = list(col.find(q, sort=[("created_at", 1)]))
    return [_feature_out(d) for d in docs]


@router.get("/incidents/{incident_id}/gis/features/by-module/{module_name}")
def list_features_by_module(incident_id: str, module_name: str, include_archived: bool = False) -> List[Dict[str, Any]]:
    col = _features(incident_id)
    _ensure_int_ids(col)
    q: Dict[str, Any] = {"incident_id": incident_id, "source_module": module_name, "deleted": {"$ne": True}}
    if not include_archived:
        q["is_archived"] = {"$ne": True}
    docs = list(col.find(q, sort=[("created_at", 1)]))
    return [_feature_out(d) for d in docs]


@router.get("/incidents/{incident_id}/gis/features/for-record")
def list_features_for_record(
    incident_id: str,
    module_name: str,
    record_type: str,
    record_id: str,
) -> List[Dict[str, Any]]:
    col = _features(incident_id)
    _ensure_int_ids(col)
    docs = list(col.find({
        "incident_id": incident_id,
        "source_module": module_name,
        "source_record_type": record_type,
        "source_record_id": record_id,
        "deleted": {"$ne": True},
    }))
    return [_feature_out(d) for d in docs]


@router.get("/incidents/{incident_id}/gis/features/{feature_id}")
def get_feature(incident_id: str, feature_id: int) -> Dict[str, Any]:
    col = _features(incident_id)
    _ensure_int_ids(col)
    doc = col.find_one({"incident_id": incident_id, "int_id": feature_id, "deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Spatial feature not found")
    return _feature_out(doc)


@router.post("/incidents/{incident_id}/gis/features", status_code=201)
def create_feature(incident_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    col = _features(incident_id)
    _ensure_int_ids(col)
    now = _utcnow()
    new_id = next_int_id(col)
    doc = {
        "_id": str(uuid.uuid4()),
        "int_id": new_id,
        "incident_id": incident_id,
        "feature_type": body.get("feature_type", ""),
        "feature_subtype": body.get("feature_subtype"),
        "geometry_type": body.get("geometry_type", ""),
        "label": body.get("label", ""),
        "description": body.get("description"),
        "status": body.get("status", "active"),
        "source_module": body.get("source_module", ""),
        "source_record_type": body.get("source_record_type", ""),
        "source_record_id": str(body.get("source_record_id") or ""),
        "geometry_wkt": body.get("geometry_wkt", ""),
        "centroid_lat": body.get("centroid_lat"),
        "centroid_lon": body.get("centroid_lon"),
        "bbox_min_lat": body.get("bbox_min_lat"),
        "bbox_min_lon": body.get("bbox_min_lon"),
        "bbox_max_lat": body.get("bbox_max_lat"),
        "bbox_max_lon": body.get("bbox_max_lon"),
        "elevation_m": body.get("elevation_m"),
        "start_time": body.get("start_time"),
        "end_time": body.get("end_time"),
        "is_planning_only": bool(body.get("is_planning_only", False)),
        "is_visible": bool(body.get("is_visible", True)),
        "is_locked": bool(body.get("is_locked", False)),
        "is_archived": False,
        "layer_key": body.get("layer_key", ""),
        "style_key": body.get("style_key"),
        "created_at": body.get("created_at") or now,
        "updated_at": now,
        "created_by": body.get("created_by"),
        "updated_by": body.get("updated_by"),
    }
    col.insert_one(doc)
    return _feature_out(doc)


@router.patch("/incidents/{incident_id}/gis/features/{feature_id}")
def update_feature(incident_id: str, feature_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    col = _features(incident_id)
    _ensure_int_ids(col)
    doc = col.find_one({"incident_id": incident_id, "int_id": feature_id, "deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Spatial feature not found")
    updatable = {
        "feature_type", "feature_subtype", "geometry_type", "label", "description", "status",
        "source_module", "source_record_type", "source_record_id", "geometry_wkt",
        "centroid_lat", "centroid_lon", "bbox_min_lat", "bbox_min_lon", "bbox_max_lat", "bbox_max_lon",
        "elevation_m", "start_time", "end_time", "is_planning_only", "is_visible", "is_locked",
        "is_archived", "layer_key", "style_key", "updated_by",
    }
    upd = {k: v for k, v in body.items() if k in updatable}
    upd["updated_at"] = _utcnow()
    col.update_one({"int_id": feature_id, "incident_id": incident_id}, {"$set": upd})
    return get_feature(incident_id, feature_id)


@router.patch("/incidents/{incident_id}/gis/features/{feature_id}/archive")
def archive_feature(incident_id: str, feature_id: int, body: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    col = _features(incident_id)
    col.update_one(
        {"incident_id": incident_id, "int_id": feature_id},
        {"$set": {"is_archived": True, "updated_at": _utcnow(), "updated_by": body.get("updated_by")}},
    )
    return get_feature(incident_id, feature_id)


# -------------------------------------------------------------------------
# Links
# -------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/gis/features/{feature_id}/links")
def list_links_for_feature(incident_id: str, feature_id: int) -> List[Dict[str, Any]]:
    col = _links(incident_id)
    _ensure_int_ids(col)
    docs = list(col.find({"incident_id": incident_id, "feature_id": feature_id, "deleted": {"$ne": True}}))
    return [_link_out(d) for d in docs]


@router.get("/incidents/{incident_id}/gis/related-features")
def list_related_features(
    incident_id: str,
    module_name: str,
    record_type: str,
    record_id: str,
) -> List[Dict[str, Any]]:
    links_col = _links(incident_id)
    _ensure_int_ids(links_col)
    link_docs = list(links_col.find({
        "incident_id": incident_id,
        "linked_module": module_name,
        "linked_record_type": record_type,
        "linked_record_id": record_id,
        "deleted": {"$ne": True},
    }))
    feature_ids = [d.get("feature_id") for d in link_docs]
    if not feature_ids:
        return []
    features_col = _features(incident_id)
    _ensure_int_ids(features_col)
    docs = list(features_col.find({"incident_id": incident_id, "int_id": {"$in": feature_ids}}))
    return [_feature_out(d) for d in docs]


@router.post("/incidents/{incident_id}/gis/links", status_code=201)
def create_link(incident_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    col = _links(incident_id)
    _ensure_int_ids(col)
    now = _utcnow()
    new_id = next_int_id(col)
    doc = {
        "_id": str(uuid.uuid4()),
        "int_id": new_id,
        "incident_id": incident_id,
        "feature_id": int(body.get("feature_id") or 0),
        "linked_module": str(body.get("linked_module") or ""),
        "linked_record_type": str(body.get("linked_record_type") or ""),
        "linked_record_id": str(body.get("linked_record_id") or ""),
        "relationship_type": str(body.get("relationship_type") or ""),
        "created_at": now,
    }
    col.insert_one(doc)
    return _link_out(doc)


@router.delete("/incidents/{incident_id}/gis/links/{link_id}", status_code=204)
def delete_link(incident_id: str, link_id: int) -> None:
    col = _links(incident_id)
    col.update_one({"incident_id": incident_id, "int_id": link_id}, {"$set": {"deleted": True}})
