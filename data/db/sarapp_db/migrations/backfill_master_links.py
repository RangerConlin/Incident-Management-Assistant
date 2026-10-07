"""One-time migration: backfill `master_link` on existing incident_personnel.

Before `master_link` existed, an `incident_personnel` document's only tie
back to the master personnel record it was copied from was the weak,
server-local `person_record` integer. This walks every `sarapp_incident_*`
database's `incident_personnel` collection and, for each document missing
`master_link`, resolves `person_record` against this server's own
`sarapp_master.personnel` and builds a `master_link` — `sync_state="linked"`
on a match, `sync_state="orphaned"` (no `master_id`) when no match is found,
per Design Documents/Instructions/mongodb_schema_decisions.md ("Master-
Incident Record Linking"). Documents that already have a `master_link`, and
documents with no `person_record` at all (never master-derived), are left
untouched — this never stubs a field onto a record with no evidence it was
ever master-derived.

Run with ``SARAPP_MONGO_URI`` set in the environment::

    python -m sarapp_db.migrations.backfill_master_links --dry-run
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_client
from sarapp_db.mongo.master_link import LINKED, ORPHANED, build_master_link
from sarapp_db.mongo.repository import BaseRepository
from sarapp_db.mongo.server_identity import get_server_id

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

_INCIDENT_PERSONNEL_COLLECTION = "incident_personnel"


class PersonnelRepository(BaseRepository):
    collection_name = MasterCollections.PERSONNEL
    soft_deletes = False


def _master_id_by_person_record(client) -> dict[int, str]:
    by_record: dict[int, str] = {}
    for person in PersonnelRepository(client["sarapp_master"]).find_many({}):
        record = person.get("person_record")
        if record is None:
            continue
        by_record[int(record)] = person["_id"]
    return by_record


def _backfill_database(db, master_id_by_record: dict[int, str], server_id: str, dry_run: bool) -> dict[str, int]:
    col = db[_INCIDENT_PERSONNEL_COLLECTION]
    stats = {"scanned": 0, "linked": 0, "orphaned": 0, "skipped_no_person_record": 0, "already_linked": 0}
    for doc in col.find({}):
        stats["scanned"] += 1
        if doc.get("master_link") is not None:
            stats["already_linked"] += 1
            continue
        record = doc.get("person_record")
        if record is None:
            stats["skipped_no_person_record"] += 1
            continue

        master_id = master_id_by_record.get(int(record))
        if master_id is not None:
            link = build_master_link(
                master_collection="personnel",
                master_id=master_id,
                master_server_origin=server_id,
                sync_state=LINKED,
            )
            stats["linked"] += 1
        else:
            link = build_master_link(
                master_collection="personnel",
                master_server_origin=server_id,
                sync_state=ORPHANED,
            )
            stats["orphaned"] += 1

        if not dry_run:
            col.update_one({"_id": doc["_id"]}, {"$set": {"master_link": link}})
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        client = get_client()
        master_id_by_record = _master_id_by_person_record(client)
    except Exception as exc:
        log.error("Unable to connect to MongoDB: %s", exc)
        sys.exit(1)

    server_id = get_server_id()
    log.info("Server id: %s", server_id)
    log.info("Master personnel records available for matching: %d", len(master_id_by_record))

    totals: dict[str, int] = {}
    for name in client.list_database_names():
        if not name.startswith("sarapp_incident_"):
            continue
        stats = _backfill_database(client[name], master_id_by_record, server_id, args.dry_run)
        for key, value in stats.items():
            totals[key] = totals.get(key, 0) + value

    log.info("Backfill complete%s: %s", " (dry run)" if args.dry_run else "", totals)


if __name__ == "__main__":
    main()
