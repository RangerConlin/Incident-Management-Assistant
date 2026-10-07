"""Per-collection "last successfully pulled from central" watermark, so
`CentralSyncLoop` only asks for what changed since last time instead of
redownloading the whole master collection on every tick.
"""

from __future__ import annotations

from pymongo.database import Database

from sarapp_db.mongo.collection_names import SystemCollections


def get_last_pulled_at(system_db: Database, collection: str) -> str | None:
    doc = system_db[SystemCollections.SYNC_PULL_CHECKPOINTS].find_one({"_id": collection})
    return doc.get("last_pulled_at") if doc else None


def set_last_pulled_at(system_db: Database, collection: str, timestamp: str) -> None:
    system_db[SystemCollections.SYNC_PULL_CHECKPOINTS].update_one(
        {"_id": collection}, {"$set": {"last_pulled_at": timestamp}}, upsert=True
    )
