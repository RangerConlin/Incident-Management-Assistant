"""Central-master sync API: the receiving end of `sarapp_db.sync`.

Mounted only in `create_app(mode="master_only")` — i.e. only inside
cloud_router's embedded central database process. LAN/cloud servers call
*into* this; it never calls out to them (each server pulls on its own
schedule — see `sarapp_db.sync.loop`).
"""

from __future__ import annotations

import hmac
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException, Query

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.int_id import next_record_id
from sarapp_db.sync.config import SYNCABLE_MASTER_COLLECTIONS
from sarapp_db.sync.relay import apply_incoming

router = APIRouter()

_TOKEN_ENV_VAR = "SARAPP_CLOUD_ROUTER_TOKEN"
_PULL_BATCH_LIMIT = 500

# A record created offline by a LAN/cloud server has no *_record_master
# field yet (see mongodb_schema_decisions.md "Personnel: central-vs-local
# record ids") — only the central catalog ever mints one, sequentially, the
# first time it sees such a record. Bumping updated_at here is what makes
# the assigned value flow back out on that server's next pull. Every
# "dual-key" master collection gets an entry here naming its own master
# field; a collection with no entry is either not dual-keyed at all, or is
# "lockdown" (central-authoritative, nothing ever created locally to mint
# an id for in the first place).
_DUAL_KEY_MASTER_FIELDS = {
    "personnel": "person_record_master",
    "equipment": "equipment_record_master",
    "vehicles": "vehicle_record_master",
    "aircraft": "aircraft_record_master",
    "hazard_types": "id_master",
    "gar_templates": "id_master",
    "canned_comm_entries": "id_master",
    "hospitals": "id_master",
    "objective_templates": "int_id_master",
    "strategy_templates": "int_id_master",
    "radio_channels": "channel_id_master",
    "safety_analysis_templates": "template_id_master",
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _assign_master_record_if_missing(collection: str, doc_id: Any) -> None:
    master_field = _DUAL_KEY_MASTER_FIELDS.get(collection)
    if master_field is None:
        return
    col = get_master_db()[collection]
    stored = col.find_one({"_id": doc_id})
    if stored is None or stored.get(master_field) is not None:
        return
    next_id = next_record_id(col, master_field)
    col.update_one(
        {"_id": doc_id},
        {"$set": {master_field: next_id, "updated_at": _utcnow()}},
    )


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
    if result in ("inserted", "applied"):
        _assign_master_record_if_missing(collection, doc["_id"])
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
