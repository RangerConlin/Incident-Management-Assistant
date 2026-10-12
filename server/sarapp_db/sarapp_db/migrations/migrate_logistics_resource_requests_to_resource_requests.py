"""One-time migration: collapse logistics_resource_requests into resource_requests.

The canonical incident resource-request collection is now `resource_requests`.
Older Mongo builds wrote ICS-213RR records to `logistics_resource_requests`.

What this script does:
  1. Enumerate all sarapp_incident_* databases.
  2. Copy records from `logistics_resource_requests` to `resource_requests`
     when a matching request id does not already exist in the canonical
     collection.
  3. Optionally drop the legacy collection after the copy with --drop-legacy.

Run with SARAPP_MONGO_URI set in the environment.

    python -m sarapp_db.migrations.migrate_logistics_resource_requests_to_resource_requests

Add --dry-run to preview changes without writing anything.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Any

from sarapp_db.mongo.database_manager import get_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

CANONICAL_COLLECTION = "resource_requests"
LEGACY_COLLECTION = "logistics_resource_requests"


def _request_key(doc: dict[str, Any]) -> Any:
    return doc.get("id") or doc.get("_id")


def _migrate_incident(client, db_name: str, *, dry_run: bool, drop_legacy: bool) -> dict[str, int]:
    db = client[db_name]
    legacy = db[LEGACY_COLLECTION]
    canonical = db[CANONICAL_COLLECTION]

    stats = {
        "dbs_scanned": 1,
        "legacy_docs": 0,
        "copied": 0,
        "skipped_existing": 0,
        "legacy_dropped": 0,
    }

    docs = list(legacy.find({}))
    stats["legacy_docs"] = len(docs)
    if not docs:
        return stats

    log.info("[%s] found %d legacy resource request docs", db_name, len(docs))
    for doc in docs:
        key = _request_key(doc)
        if canonical.find_one({"id": key}) or canonical.find_one({"_id": doc.get("_id")}):
            stats["skipped_existing"] += 1
            continue
        if not dry_run:
            canonical.insert_one(dict(doc))
        stats["copied"] += 1

    if drop_legacy:
        log.info("[%s] dropping legacy collection %s", db_name, LEGACY_COLLECTION)
        if not dry_run:
            legacy.drop()
        stats["legacy_dropped"] = 1

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate logistics_resource_requests to resource_requests."
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing anything.")
    parser.add_argument(
        "--drop-legacy",
        action="store_true",
        help="Drop logistics_resource_requests after copying records.",
    )
    args = parser.parse_args()

    if not os.environ.get("SARAPP_MONGO_URI"):
        log.error("SARAPP_MONGO_URI environment variable is not set.")
        sys.exit(1)

    try:
        client = get_client()
    except Exception as exc:
        log.error("Unable to connect to MongoDB: %s", exc)
        sys.exit(1)

    if args.dry_run:
        log.info("DRY RUN - no data will be written.")

    incident_dbs = [
        name for name in client.list_database_names()
        if name.startswith("sarapp_incident_")
    ]
    totals = {
        "dbs_scanned": 0,
        "legacy_docs": 0,
        "copied": 0,
        "skipped_existing": 0,
        "legacy_dropped": 0,
        "errors": 0,
    }
    for db_name in incident_dbs:
        try:
            stats = _migrate_incident(
                client,
                db_name,
                dry_run=args.dry_run,
                drop_legacy=args.drop_legacy,
            )
            for key, value in stats.items():
                totals[key] += value
        except Exception as exc:
            totals["errors"] += 1
            log.error("[%s] migration failed: %s", db_name, exc)

    log.info("Migration complete%s", " (dry run)" if args.dry_run else "")
    log.info("Databases scanned:       %d", totals["dbs_scanned"])
    log.info("Legacy docs found:       %d", totals["legacy_docs"])
    log.info("Copied to canonical:     %d", totals["copied"])
    log.info("Skipped existing docs:   %d", totals["skipped_existing"])
    log.info("Legacy collections drop: %d", totals["legacy_dropped"])
    log.info("Errors:                  %d", totals["errors"])

    if totals["errors"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
