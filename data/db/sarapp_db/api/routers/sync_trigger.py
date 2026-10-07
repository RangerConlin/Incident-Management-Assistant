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

    run_one_tick()
    return {"synced": True}
