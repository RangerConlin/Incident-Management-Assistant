"""One-time migration: backfill `section` on resource-request approvals.

`logistics_resource_requests.py`'s approval records now carry a `section`
field (one of "requesting", "logistics", "finance") so the UI can group
required approvals by ICS-213RR responsibility tier instead of a flat
chronological list. Approval records written before this field existed
have no `section` — this script backfills one for them, derived from the
approval's `action` the same way the router defaults it for new records.

Run with SARAPP_MONGO_URI set in the environment.

    python -m sarapp_db.migrations.backfill_resource_request_approval_section

Add --dry-run to preview changes without writing anything.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

from sarapp_db.mongo.database_manager import get_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

COLLECTION = "resource_requests"

# Mirrors ACTION_SECTION_MAP / FINANCE_ACTION_MAP in
# api/routers/logistics_resource_requests.py — kept as a plain copy here
# rather than imported, since migrations are meant to stand on their own
# even if the router's mapping changes later.
ACTION_SECTION_MAP = {
    "SUBMIT": "requesting",
    "REVIEW": "logistics",
    "APPROVE": "logistics",
    "DENY": "logistics",
    "CANCEL": "requesting",
    "REOPEN": "requesting",
    "FINANCE_APPROVE": "finance",
    "FINANCE_DENY": "finance",
}


def _migrate_incident(client, db_name: str, *, dry_run: bool) -> dict[str, int]:
    db = client[db_name]
    col = db[COLLECTION]

    stats = {"dbs_scanned": 1, "requests_scanned": 0, "approvals_backfilled": 0, "requests_updated": 0}

    for doc in col.find({"approvals": {"$exists": True, "$ne": []}}):
        stats["requests_scanned"] += 1
        approvals = doc.get("approvals") or []
        changed = False
        for approval in approvals:
            if approval.get("section"):
                continue
            action = str(approval.get("action", "")).upper()
            approval["section"] = ACTION_SECTION_MAP.get(action, "logistics")
            stats["approvals_backfilled"] += 1
            changed = True
        if changed:
            log.info("[%s] request %s: backfilled %d approval(s)", db_name, doc.get("id"), len(approvals))
            if not dry_run:
                col.update_one({"_id": doc["_id"]}, {"$set": {"approvals": approvals}})
            stats["requests_updated"] += 1

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill `section` on resource-request approvals.")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing anything.")
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

    incident_dbs = [name for name in client.list_database_names() if name.startswith("sarapp_incident_")]
    totals = {"dbs_scanned": 0, "requests_scanned": 0, "approvals_backfilled": 0, "requests_updated": 0, "errors": 0}
    for db_name in incident_dbs:
        try:
            stats = _migrate_incident(client, db_name, dry_run=args.dry_run)
            for key, value in stats.items():
                totals[key] += value
        except Exception as exc:
            totals["errors"] += 1
            log.error("[%s] migration failed: %s", db_name, exc)

    log.info("Migration complete%s", " (dry run)" if args.dry_run else "")
    log.info("Databases scanned:       %d", totals["dbs_scanned"])
    log.info("Requests scanned:        %d", totals["requests_scanned"])
    log.info("Requests updated:        %d", totals["requests_updated"])
    log.info("Approvals backfilled:    %d", totals["approvals_backfilled"])
    log.info("Errors:                  %d", totals["errors"])

    if totals["errors"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
