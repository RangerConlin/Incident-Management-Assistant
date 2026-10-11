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

from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.post("/resync")
def force_resync() -> dict[str, Any]:
    from sarapp_db.sync import config
    from sarapp_db.sync.loop import run_one_tick

    if not config.sync_enabled():
        return {"synced": False, "reason": "Central master sync is not configured on this server."}

    result = run_one_tick()
    failed_collections = result.get("pull_failed_collections") or []
    outbox_failed_count = int(result.get("outbox_failed_count") or 0)
    if failed_collections or outbox_failed_count:
        reason = "Central master sync is configured, but this server could not complete a sync tick."
        if failed_collections:
            reason += f" Pull failed for: {', '.join(failed_collections)}."
        if outbox_failed_count:
            reason += f" {outbox_failed_count} queued local change(s) could not be pushed."
        return {"synced": False, "reason": reason, "details": result}
    return {"synced": True, "details": result}


@router.get("/status")
def sync_status() -> dict[str, Any]:
    from sarapp_db.sync.status import get_sync_status

    return get_sync_status()
