"""Central-master sync API: the receiving end of `sarapp_db.sync`.

Mounted only in `create_app(mode="master_only")` — i.e. only inside
cloud_router's embedded central database process. LAN/cloud servers call
*into* this; it never calls out to them (each server pulls on its own
schedule — see `sarapp_db.sync.loop`).
"""

from __future__ import annotations

import hmac
import os
from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException, Query

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.sync.config import SYNCABLE_MASTER_COLLECTIONS
from sarapp_db.sync.relay import apply_incoming

router = APIRouter()

_TOKEN_ENV_VAR = "SARAPP_CLOUD_ROUTER_TOKEN"
_PULL_BATCH_LIMIT = 500


def _require_token(x_sarapp_sync_token: str | None) -> None:
    expected = os.environ.get(_TOKEN_ENV_VAR, "").strip()
    if not expected or not hmac.compare_digest(str(x_sarapp_sync_token or ""), expected):
        raise HTTPException(status_code=401, detail="Invalid or missing sync token")


def _require_syncable(collection: str) -> None:
    if collection not in SYNCABLE_MASTER_COLLECTIONS:
        raise HTTPException(status_code=404, detail=f"'{collection}' is not a syncable collection")


@router.post("/push")
def push(
    body: dict[str, Any] = Body(...),
    x_sarapp_sync_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_token(x_sarapp_sync_token)
    collection = str(body.get("collection") or "")
    _require_syncable(collection)

    op = body.get("op") or "upsert"
    if op == "delete":
        doc_id = body.get("doc_id")
        deleted_at = body.get("updated_at")
        if not doc_id:
            raise HTTPException(status_code=400, detail="doc_id is required for a delete")
        db = get_master_db()
        tombstone = {"_id": doc_id, "deleted": True, "updated_at": deleted_at}
        result = apply_incoming(db, collection, tombstone)
        # Retained separately from the real collection (which apply_incoming
        # just hard-deleted the document out of, same as any other
        # receiver) specifically so a later "what changed since X" pull —
        # by a server that hasn't seen this delete yet — can still discover
        # it. A literal removal with nothing left behind would be invisible
        # to that query. Written unconditionally, even if the document was
        # already absent here, so a server that never had this record still
        # learns not to re-create it from some other stale source.
        db[MasterCollections.SYNC_TOMBSTONES].update_one(
            {"_id": f"{collection}:{doc_id}"},
            {"$set": {"collection": collection, "doc_id": doc_id, "deleted_at": deleted_at}},
            upsert=True,
        )
        return {"result": result}

    doc = body.get("doc")
    if not isinstance(doc, dict) or not doc.get("_id"):
        raise HTTPException(status_code=400, detail="doc with an _id is required")

    result = apply_incoming(get_master_db(), collection, doc)
    return {"result": result}


@router.get("/pull")
def pull(
    collection: str = Query(...),
    since: str = Query(""),
    x_sarapp_sync_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_token(x_sarapp_sync_token)
    _require_syncable(collection)

    db = get_master_db()
    query: dict[str, Any] = {"updated_at": {"$gt": since}} if since else {}
    docs = list(db[collection].find(query))

    tombstone_query: dict[str, Any] = {"collection": collection}
    tombstone_query["deleted_at"] = {"$gt": since} if since else {"$exists": True}
    tombstones = [
        {"_id": entry["doc_id"], "deleted": True, "updated_at": entry["deleted_at"]}
        for entry in db[MasterCollections.SYNC_TOMBSTONES].find(tombstone_query)
    ]

    combined = sorted(docs + tombstones, key=lambda d: str(d.get("updated_at") or ""))[:_PULL_BATCH_LIMIT]
    return {"docs": combined}
