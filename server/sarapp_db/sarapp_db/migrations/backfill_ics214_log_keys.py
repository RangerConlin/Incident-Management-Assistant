"""Backfill the canonical ``log_keys`` field on existing ICS-214 entries.

This migration intentionally does not guess a built-in log from organization
names. Existing entity associations remain intact; the field is initialized to
an empty list so all documents use the new canonical shape.

Run before deploying built-in log identities::

    python -m sarapp_db.migrations.backfill_ics214_log_keys --dry-run
    python -m sarapp_db.migrations.backfill_ics214_log_keys
"""
from __future__ import annotations

import argparse

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import DB_INCIDENT_PREFIX
from sarapp_db.mongo.mongo_client import get_client
from sarapp_db.mongo.repository import BaseRepository


class Ics214EntriesRepository(BaseRepository):
    collection_name = IncidentCollections.ICS_214_ENTRIES
    soft_deletes = False


def migrate(*, dry_run: bool = False) -> dict[str, int]:
    client = get_client()
    changed = 0
    for database_name in client.list_database_names():
        if not database_name.startswith(DB_INCIDENT_PREFIX):
            continue
        repository = Ics214EntriesRepository(client[database_name])
        rows = repository.find_many({"log_keys": {"$exists": False}})
        changed += len(rows)
        if dry_run:
            continue
        for row in rows:
            repository.update_one(row["_id"], {"log_keys": []})
    return {"ics214_entries_backfilled": changed}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(migrate(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
