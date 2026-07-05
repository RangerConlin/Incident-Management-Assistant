"""
One-time migration: move embedded task narrative arrays into the task_narratives collection.

Previously, narrative entries were pushed into a `narrative` array on each task document.
The task_narratives router and bridge now read/write to the separate `task_narratives`
collection exclusively. Any entries still embedded in task documents are invisible to
the current application.

What this script does:
  1. Enumerate all sarapp_incident_* databases.
  2. For each task document that has a non-empty `narrative` array, insert each entry
     as a flat document in `task_narratives` (skipping any that already exist there to
     make the script safe to re-run).
  3. Unset the embedded `narrative` array from the task document once all entries
     for that task are successfully migrated.

Run with SARAPP_MONGO_URI set in the environment (the same variable the server uses).

    python -m sarapp_db.migrations.migrate_narrative_embedded_to_collection

Add --dry-run to preview what would happen without writing anything.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import uuid
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _migrate_incident(client, db_name: str, dry_run: bool) -> dict:
    """Migrate one incident database. Returns a stats dict."""
    db = client[db_name]
    tasks_col = db["tasks"]
    narratives_col = db["task_narratives"]

    stats = {"tasks_scanned": 0, "entries_migrated": 0, "entries_skipped": 0, "tasks_cleared": 0, "errors": 0}

    # Only fetch tasks that have a non-empty narrative array
    for task in tasks_col.find({"narrative": {"$exists": True, "$not": {"$size": 0}}}):
        stats["tasks_scanned"] += 1
        task_int_id = task.get("int_id")
        embedded = task.get("narrative") or []
        if not embedded:
            continue

        task_migrated = 0
        task_failed = 0

        for entry in embedded:
            # Build the canonical task_narratives document shape
            ts = entry.get("timestamp") or _now_iso()
            narrative_text = entry.get("narrative") or entry.get("text") or ""
            entered_by = entry.get("entered_by") or ""
            team_num = entry.get("team_num") or ""
            critical_raw = entry.get("critical", 0)
            critical = 1 if critical_raw in (True, 1, "1", "true", "True") else 0

            # Dedup check: skip if a document with the same task_id + timestamp +
            # narrative text already exists in the target collection.
            existing = narratives_col.find_one(
                {"task_id": task_int_id, "timestamp": ts, "narrative": narrative_text}
            )
            if existing:
                stats["entries_skipped"] += 1
                continue

            doc = {
                "_id": uuid.uuid4().hex,
                "task_id": task_int_id,
                "timestamp": ts,
                "narrative": narrative_text,
                "entered_by": entered_by,
                "team_num": team_num,
                "critical": critical,
            }

            try:
                if not dry_run:
                    narratives_col.insert_one(doc)
                task_migrated += 1
                stats["entries_migrated"] += 1
                log.debug("  [%s] task %s: migrated entry at %s", db_name, task_int_id, ts)
            except Exception as exc:
                log.error("  [%s] task %s: failed to insert entry (%s)", db_name, task_int_id, exc)
                task_failed += 1
                stats["errors"] += 1

        # Only clear the embedded array when every entry for this task was either
        # migrated or was already present in the target collection (no failures).
        if task_failed == 0:
            if not dry_run:
                tasks_col.update_one({"_id": task["_id"]}, {"$unset": {"narrative": ""}})
            stats["tasks_cleared"] += 1
            log.info(
                "  [%s] task int_id=%s: migrated %d, skipped %d (already present)",
                db_name, task_int_id, task_migrated, len(embedded) - task_migrated - task_failed,
            )
        else:
            log.warning(
                "  [%s] task int_id=%s: %d entries failed — embedded array NOT cleared",
                db_name, task_int_id, task_failed,
            )

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate embedded task narratives to task_narratives collection.")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing anything.")
    args = parser.parse_args()

    mongo_uri = os.environ.get("SARAPP_MONGO_URI")
    if not mongo_uri:
        log.error("SARAPP_MONGO_URI environment variable is not set.")
        sys.exit(1)

    try:
        from pymongo import MongoClient
    except ImportError:
        log.error("pymongo is not installed.")
        sys.exit(1)

    client = MongoClient(mongo_uri)

    if args.dry_run:
        log.info("DRY RUN — no data will be written.")

    incident_dbs = [
        name for name in client.list_database_names()
        if name.startswith("sarapp_incident_")
    ]

    if not incident_dbs:
        log.info("No incident databases found. Nothing to do.")
        return

    log.info("Found %d incident database(s): %s", len(incident_dbs), incident_dbs)

    totals: dict = {"tasks_scanned": 0, "entries_migrated": 0, "entries_skipped": 0, "tasks_cleared": 0, "errors": 0}

    for db_name in incident_dbs:
        log.info("Processing %s ...", db_name)
        stats = _migrate_incident(client, db_name, dry_run=args.dry_run)
        for k, v in stats.items():
            totals[k] += v

    client.close()

    log.info("")
    log.info("=== Migration complete%s ===", " (dry run)" if args.dry_run else "")
    log.info("  Incident databases:  %d", len(incident_dbs))
    log.info("  Tasks scanned:       %d", totals["tasks_scanned"])
    log.info("  Entries migrated:    %d", totals["entries_migrated"])
    log.info("  Entries skipped:     %d  (already in task_narratives)", totals["entries_skipped"])
    log.info("  Task arrays cleared: %d", totals["tasks_cleared"])
    log.info("  Errors:              %d", totals["errors"])

    if totals["errors"]:
        log.warning("Some entries failed. Re-run the script to retry — it is safe to run multiple times.")
        sys.exit(2)


if __name__ == "__main__":
    main()
