"""Lets a desktop client force an immediate resync with the central master
database, instead of waiting for `sync.loop.CentralSyncLoop`'s next
periodic tick (see the "Refresh" / "Resync" button on the personnel and
equipment master-catalog panels).

Mounted on every LAN/cloud/offline server (`create_app(mode="full")`) —
not the central sync-receiving API in `sync.py`, which is mounted only on
cloud_router's embedded central database (`mode="master_only"`). This
router calls out *to* that one; it never serves it.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/resync")
def force_resync() -> dict[str, Any]:
    from sarapp_db.sync import config
    from sarapp_db.sync.loop import run_one_tick

    if not config.sync_enabled():
        return {"synced": False, "reason": "Central master sync is not configured on this server."}

    try:
        result = run_one_tick()
    except Exception as exc:
        logger.exception("Manual central master resync failed.")
        return {
            "synced": False,
            "reason": f"Central master sync failed before it could complete: {exc}",
        }

    if not isinstance(result, dict):
        return {
            "synced": False,
            "reason": "Central master sync did not return a status summary.",
            "details": {"result_type": type(result).__name__},
        }

    failed_collections = [str(collection) for collection in (result.get("pull_failed_collections") or [])]
    try:
        outbox_failed_count = int(result.get("outbox_failed_count") or 0)
    except (TypeError, ValueError):
        outbox_failed_count = 0
    errors = result.get("errors") or []
    if failed_collections or outbox_failed_count or errors:
        reason = "Central master sync is configured, but this server could not complete a sync tick."
        if failed_collections:
            reason += f" Pull failed for: {', '.join(failed_collections)}."
        if outbox_failed_count:
            reason += f" {outbox_failed_count} queued local change(s) could not be pushed."
        if errors:
            first_error = errors[0]
            collection = first_error.get("collection") or first_error.get("phase") or "sync"
            reason += f" First error: {collection}: {first_error.get('error') or 'unknown error'}."
        return {"synced": False, "reason": reason, "details": result}
    return {"synced": True, "details": result}


@router.get("/status")
def sync_status() -> dict[str, Any]:
    from sarapp_db.sync.status import get_sync_status

    return get_sync_status()


@router.post("/local-catalog/{collection}/reset")
def reset_local_catalog(collection: str) -> dict[str, Any]:
    """Clear one local master catalog so it can be rebuilt from central.

    This intentionally bypasses each collection's ordinary DELETE route:
    a local reset must not relay tombstones back to the central master.
    """
    from sarapp_db.mongo.collection_names import SystemCollections
    from sarapp_db.mongo.database_manager import get_master_db, get_system_db, is_central_master_db
    from sarapp_db.sync import checkpoint, config

    if collection not in config.SYNCABLE_MASTER_COLLECTIONS:
        raise HTTPException(status_code=404, detail=f"'{collection}' is not a resettable sync catalog")

    master_db = get_master_db()
    if is_central_master_db(master_db):
        raise HTTPException(status_code=400, detail="Local catalog reset is not available on the central master")

    result = master_db[collection].delete_many({})
    system_db = get_system_db()
    checkpoint.clear_last_pulled_at(system_db, collection)
    outbox_result = system_db[SystemCollections.SYNC_STATE].delete_many({"collection": collection})
    return {
        "reset": True,
        "collection": collection,
        "deleted_count": int(result.deleted_count),
        "cleared_outbox_count": int(outbox_result.deleted_count),
    }
