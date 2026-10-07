"""Core sync relay logic: applying an incoming document (from a push or a
pull) to a target database, and the write-time hook `BaseRepository` calls
for every master-collection write.

Conflict policy (see Design Documents/Instructions/mongodb_schema_decisions.md
"Central-Master Sync Relay"): pure last-write-wins by `updated_at`. Two
genuinely simultaneous edits to the same record are not a realistic case to
design around — resolved explicitly in favor of simplicity over a
conflict-review workflow. Whichever write has the newer timestamp always
wins outright; there is nothing to log or reconcile.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Literal

from pymongo.database import Database

from sarapp_db.sync import config, outbox
from sarapp_db.sync.central_client import push_delete, push_one

logger = logging.getLogger(__name__)

ApplyResult = Literal["inserted", "applied", "skipped_same_or_older", "deleted", "already_absent"]

_IGNORED_FIELDS = {"_id", "created_at", "updated_at"}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _content_equal(a: dict[str, Any], b: dict[str, Any]) -> bool:
    strip = lambda d: {k: v for k, v in d.items() if k not in _IGNORED_FIELDS}
    return strip(a) == strip(b)


def apply_incoming(db: Database, collection: str, doc: dict[str, Any]) -> ApplyResult:
    """Apply one incoming document to `db[collection]`.

    Safe to call repeatedly with the same document (idempotent) —
    reapplying an already-applied doc is a no-op (`skipped_same_or_older`).

    `doc.get("deleted") is True` is treated as a tombstone — a sync-protocol
    marker, independent of whatever meaning (or lack of one) a given
    collection's own `soft_deletes` setting gives that field — and causes
    the matching local document to be hard-deleted rather than upserted.
    This is how a real deletion on a `soft_deletes=False` collection (e.g.
    `equipment`, which hard-deletes) still propagates: the delete is relayed
    as a tombstone doc, applied as a tombstone everywhere it's pulled, and
    only ever hard-removed, never left behind as an inert flag nothing
    reads. A `soft_deletes=True` collection's own soft-deletes already
    relay for free through the ordinary upsert path below — no separate
    handling needed there.
    """
    if doc.get("deleted") is True:
        return _apply_incoming_delete(db, collection, doc)

    col = db[collection]
    doc_id = doc.get("_id")
    existing = col.find_one({"_id": doc_id}) if doc_id else None

    if existing is None:
        col.insert_one(dict(doc))
        return "inserted"

    if _content_equal(existing, doc):
        return "skipped_same_or_older"

    incoming_updated = str(doc.get("updated_at") or "")
    existing_updated = str(existing.get("updated_at") or "")

    if incoming_updated >= existing_updated:
        col.replace_one({"_id": doc_id}, dict(doc))
        return "applied"

    return "skipped_same_or_older"


def _apply_incoming_delete(db: Database, collection: str, tombstone: dict[str, Any]) -> ApplyResult:
    col = db[collection]
    doc_id = tombstone.get("_id")
    existing = col.find_one({"_id": doc_id}) if doc_id else None
    if existing is None:
        return "already_absent"

    incoming_updated = str(tombstone.get("updated_at") or "")
    existing_updated = str(existing.get("updated_at") or "")
    if existing_updated > incoming_updated:
        # Existing was touched strictly after this deletion happened
        # elsewhere — newest timestamp wins, so the later edit survives.
        return "skipped_same_or_older"

    col.delete_one({"_id": doc_id})
    return "deleted"


def relay_local_delete(db: Database, collection: str, doc_id: str) -> None:
    """Called by `BaseRepository.delete_one` right after a hard delete on a
    syncable master collection. Same best-effort contract as
    `relay_local_write` — never raises."""
    if collection not in config.SYNCABLE_MASTER_COLLECTIONS:
        return
    try:
        _relay_delete_or_enqueue(db, collection, doc_id)
    except Exception:
        logger.exception("Central sync delete relay failed for %s/%s", collection, doc_id)


def _relay_delete_or_enqueue(db: Database, collection: str, doc_id: str) -> None:
    from sarapp_db.mongo.database_manager import get_system_db

    if not config.sync_enabled():
        return
    deleted_at = _utcnow_iso()
    sent = push_delete(
        config.central_master_url(), config.sync_token(), collection=collection, doc_id=doc_id, deleted_at=deleted_at
    )
    if not sent:
        outbox.enqueue(get_system_db(), collection=collection, doc_id=doc_id, op="delete", timestamp=deleted_at)


def relay_local_write(db: Database, collection: str, doc: dict[str, Any]) -> None:
    """Called by `BaseRepository` right after a write to a syncable master
    collection. Best-effort: never raises — a sync failure must never break
    the write that triggered it, matching `_broadcast()`'s own contract.
    """
    if collection not in config.SYNCABLE_MASTER_COLLECTIONS:
        return
    try:
        _relay_or_enqueue(db, collection, doc)
    except Exception:
        logger.exception("Central sync relay failed for %s/%s", collection, doc.get("_id"))


def _relay_or_enqueue(db: Database, collection: str, doc: dict[str, Any]) -> None:
    from sarapp_db.mongo.database_manager import get_system_db

    if not config.sync_enabled():
        return
    sent = push_one(config.central_master_url(), config.sync_token(), collection=collection, doc=doc)
    if not sent:
        outbox.enqueue(get_system_db(), collection=collection, doc_id=str(doc.get("_id")))
