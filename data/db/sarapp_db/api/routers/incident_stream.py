"""Generic IncidentCache snapshot + live-update WebSocket endpoint.

Serves every collection in `IncidentCollections` for a given incident, so the
desktop IncidentCache can bulk-load on incident open and then stay current via
the WebSocket without any per-module wiring. New collections show up here
automatically as they're added to IncidentCollections.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from sarapp_db.api.ws_hub import hub
from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.json_safe import json_safe

router = APIRouter()

_ALL_COLLECTIONS: List[str] = sorted(
    {
        value
        for name, value in vars(IncidentCollections).items()
        if not name.startswith("_") and isinstance(value, str)
    }
)

DEFAULT_MAX_SNAPSHOT_MB = 150
DEFAULT_MAX_COLLECTION_DOCS = 5000
DEFAULT_MAX_HEAVY_COLLECTION_DOCS = 500

_HEAVY_COLLECTIONS = {
    IncidentCollections.AUDIT_LOGS,
    IncidentCollections.ATTACHMENTS,
    IncidentCollections.CHECKIN_HISTORY,
    IncidentCollections.COMMUNICATIONS_LOG,
    IncidentCollections.COMMS_LOG_AUDIT,
    IncidentCollections.FORM_INSTANCE_AUDIT,
    IncidentCollections.FORM_INSTANCE_EXPORTS,
    IncidentCollections.FORM_INSTANCE_REVISIONS,
    IncidentCollections.ICS_214_LOGS,
    IncidentCollections.INCIDENT_JOURNAL,
    IncidentCollections.INTEL_LOG,
    IncidentCollections.NOTIFICATIONS,
    IncidentCollections.PIO_DISTRIBUTION_LOG,
    IncidentCollections.PIO_GENERATED_DOCUMENTS,
    IncidentCollections.PIO_MESSAGE_REVISIONS,
    IncidentCollections.PIO_MISINFORMATION_TIMELINE,
    IncidentCollections.TASK_NARRATIVES,
    IncidentCollections.UNIT_LOGS,
}

_RECENT_SORT_FIELDS = (
    "updated_at",
    "created_at",
    "timestamp",
    "timestamp_utc",
    "ts_utc",
    "logged_at",
    "_id",
)


def _bounded_int(value: int, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return max(minimum, min(parsed, maximum))


def _limit_for_collection(name: str, max_collection_docs: int, max_heavy_collection_docs: int) -> int:
    if name in _HEAVY_COLLECTIONS:
        return max_heavy_collection_docs
    return max_collection_docs


def _estimate_json_bytes(value: Any) -> int:
    try:
        return len(json.dumps(value, default=str, separators=(",", ":")).encode("utf-8"))
    except Exception:
        return 0


def _recent_sort_for_collection(db, name: str) -> list[tuple[str, int]]:
    try:
        sample = db[name].find_one({"deleted": {"$ne": True}}) or {}
    except Exception:
        sample = {}
    for field in _RECENT_SORT_FIELDS:
        if field == "_id" or field in sample:
            return [(field, -1)]
    return [("_id", -1)]


@router.get("/incidents/{incident_id}/snapshot")
def get_snapshot(
    incident_id: str,
    collections: Optional[str] = Query(default=None, description="Comma-separated collection names; omit for all"),
    max_snapshot_mb: int = Query(default=DEFAULT_MAX_SNAPSHOT_MB, ge=1, le=1024),
    max_collection_docs: int = Query(default=DEFAULT_MAX_COLLECTION_DOCS, ge=1, le=100000),
    max_heavy_collection_docs: int = Query(default=DEFAULT_MAX_HEAVY_COLLECTION_DOCS, ge=1, le=10000),
) -> Dict[str, Any]:
    """Return bounded current documents for the requested collections.

    Small active collections are returned up to ``max_collection_docs``.
    Heavy/history collections are capped lower and sorted recent-first. The
    response includes metadata describing any truncation so clients can page
    older data from purpose-built endpoints when needed.
    """
    db = get_incident_db(incident_id)
    max_snapshot_bytes = _bounded_int(
        max_snapshot_mb,
        default=DEFAULT_MAX_SNAPSHOT_MB,
        minimum=1,
        maximum=1024,
    ) * 1024 * 1024
    max_collection_docs = _bounded_int(
        max_collection_docs,
        default=DEFAULT_MAX_COLLECTION_DOCS,
        minimum=1,
        maximum=100000,
    )
    max_heavy_collection_docs = _bounded_int(
        max_heavy_collection_docs,
        default=DEFAULT_MAX_HEAVY_COLLECTION_DOCS,
        minimum=1,
        maximum=10000,
    )
    names = collections.split(",") if collections else _ALL_COLLECTIONS
    snapshot: Dict[str, List[Dict[str, Any]]] = {}
    meta: Dict[str, Any] = {
        "policy": {
            "max_snapshot_mb": max_snapshot_mb,
            "max_collection_docs": max_collection_docs,
            "max_heavy_collection_docs": max_heavy_collection_docs,
            "heavy_collections": sorted(_HEAVY_COLLECTIONS),
        },
        "collections": {},
        "truncated": {},
        "estimated_bytes": 0,
        "truncated_by_budget": False,
    }
    for name in names:
        name = name.strip()
        if not name:
            continue
        # `$ne: True` rather than `False` so documents that predate the
        # `deleted` field (written before this collection went through
        # BaseRepository) still show up instead of vanishing from the cache.
        limit = _limit_for_collection(name, max_collection_docs, max_heavy_collection_docs)
        total = db[name].count_documents({"deleted": {"$ne": True}})
        cursor = db[name].find({"deleted": {"$ne": True}})
        if name in _HEAVY_COLLECTIONS:
            cursor = cursor.sort(_recent_sort_for_collection(db, name))
        docs = list(cursor.limit(limit))
        # Documents from collections that predate BaseRepository can carry
        # BSON types (ObjectId, raw datetime) a JSON encoder can't handle,
        # anywhere in the document, not just `_id` — sanitize recursively
        # rather than touching the stored value.
        safe_docs = [json_safe(doc) for doc in docs]
        if name in _HEAVY_COLLECTIONS:
            safe_docs = list(reversed(safe_docs))
        collection_bytes = _estimate_json_bytes(safe_docs)
        if meta["estimated_bytes"] + collection_bytes > max_snapshot_bytes:
            meta["truncated_by_budget"] = True
            meta["truncated"][name] = {
                "loaded": 0,
                "total": total,
                "limit": limit,
                "reason": "snapshot byte budget",
            }
            snapshot[name] = []
            meta["collections"][name] = {
                "loaded": 0,
                "total": total,
                "limit": limit,
                "heavy": name in _HEAVY_COLLECTIONS,
                "estimated_bytes": 0,
            }
            continue
        snapshot[name] = safe_docs
        meta["estimated_bytes"] += collection_bytes
        collection_meta = {
            "loaded": len(safe_docs),
            "total": total,
            "limit": limit,
            "heavy": name in _HEAVY_COLLECTIONS,
            "estimated_bytes": collection_bytes,
        }
        meta["collections"][name] = collection_meta
        if total > len(safe_docs):
            meta["truncated"][name] = {
                "loaded": len(safe_docs),
                "total": total,
                "limit": limit,
                "reason": "collection document limit",
            }
    return {"incident_id": incident_id, "collections": snapshot, "meta": meta}


@router.websocket("/incidents/{incident_id}/ws")
async def incident_ws(websocket: WebSocket, incident_id: str) -> None:
    await hub.connect(incident_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(incident_id, websocket)
