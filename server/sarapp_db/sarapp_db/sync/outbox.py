"""Local outbox of master-collection writes still pending delivery to the
central database — populated when an immediate push fails (central
unreachable, or sync not configured at write time), drained by
`CentralSyncLoop` on its next tick.

Stored in `sarapp_system.sync_state` (see collection_names.py).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pymongo.database import Database

from sarapp_db.mongo.collection_names import SystemCollections


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def enqueue(
    system_db: Database,
    *,
    collection: str,
    doc_id: str,
    op: str = "upsert",
    timestamp: str | None = None,
) -> None:
    """Queue `collection`/`doc_id` for retry, replacing any existing queued
    entry for that same document (always re-sends the current state on
    retry, not a stale queued snapshot).

    `op="upsert"` (the default) re-reads the document's current state from
    the local collection at drain time. `op="delete"` can't do that — the
    document is already gone locally — so `timestamp` (the tombstone's
    `deleted_at`) is captured now and replayed as-is on retry.
    """
    col = system_db[SystemCollections.SYNC_STATE]
    fields: dict[str, Any] = {
        "collection": collection,
        "doc_id": doc_id,
        "op": op,
        "last_queued_at": _utcnow_iso(),
    }
    if op == "delete":
        fields["deleted_at"] = timestamp
    col.update_one(
        {"collection": collection, "doc_id": doc_id},
        {
            "$set": fields,
            "$setOnInsert": {"_id": str(uuid.uuid4()), "attempts": 0},
        },
        upsert=True,
    )


def list_pending(system_db: Database) -> list[dict[str, Any]]:
    return list(system_db[SystemCollections.SYNC_STATE].find({}))


def mark_sent(system_db: Database, entry_id: str) -> None:
    system_db[SystemCollections.SYNC_STATE].delete_one({"_id": entry_id})


def record_failure(system_db: Database, entry_id: str, error: str) -> None:
    system_db[SystemCollections.SYNC_STATE].update_one(
        {"_id": entry_id},
        {"$set": {"last_error": error, "last_attempt_at": _utcnow_iso()}, "$inc": {"attempts": 1}},
    )
