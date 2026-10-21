"""One-time migration: backfill `kind` on existing resource_type records.

Stage 1 of the resource-packages work adds an explicit Resource Kind field
(what the resource *is*, e.g. "Fire Engine", "Ground Search Team") to the
Resource Type Library, distinct from the existing `category` (broad class:
Personnel/Vehicle/Aircraft/Equipment/Team-Unit/...) and from any formal
FEMA/NIMS type recorded in `fema_mappings`.

Every resource_type document that predates this field has no `kind` at all.
Per the migration rule ("no invented data"), this script never guesses a
new classification -- it only copies forward information the record
already carries: the existing planning display name (`resource_name`),
falling back to the internal `name` when no display name was set. Both of
those already describe "what the resource is" in the vast majority of
existing records, so copying one forward is a safe default, not an
invention; an operator can always refine it later through the editor.

Only documents with no `kind` (missing, None, or empty string) are touched.

Run with SARAPP_MONGO_URI set in the environment::

    python -m sarapp_db.migrations.backfill_resource_type_kind --dry-run
    python -m sarapp_db.migrations.backfill_resource_type_kind
"""
from __future__ import annotations

import argparse
import logging
import sys

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


def backfill_resource_type_kind(*, dry_run: bool = False) -> int:
    """Backfill `kind` on every sarapp_master-like database's resource_types.

    Walks `sarapp_master` and, if present, `sarapp_central_master` (the
    cloud_router embedded catalog shares the same schema). Returns the
    number of documents updated (or that would be updated, under
    --dry-run).
    """
    client = get_client()
    updated = 0
    for db_name in ("sarapp_master", "sarapp_central_master"):
        if db_name not in client.list_database_names():
            continue
        col = client[db_name][MasterCollections.RESOURCE_TYPES]
        cursor = col.find({"$or": [{"kind": {"$exists": False}}, {"kind": None}, {"kind": ""}]})
        for doc in cursor:
            default_kind = str(doc.get("resource_name") or doc.get("name") or "").strip()
            if not default_kind:
                continue
            log.info(
                "%s.resource_types[%s]: kind <- %r",
                db_name,
                doc.get("resource_type_id") or doc.get("_id"),
                default_kind,
            )
            if not dry_run:
                col.update_one({"_id": doc["_id"]}, {"$set": {"kind": default_kind}})
            updated += 1
    log.info("%s %d resource_type document(s).", "Would update" if dry_run else "Updated", updated)
    return updated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing them.")
    args = parser.parse_args(argv)
    backfill_resource_type_kind(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
