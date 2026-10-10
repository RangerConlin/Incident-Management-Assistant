"""One-time seed: populate the `certification_types` collection from the
previously-hardcoded `modules/personnel/models/cert_catalog.py` CATALOG.

Before this migration, `cert_catalog.CATALOG` was "authoritative in
production" (its own docstring) — a Python list, editable only by a
developer using `modules/devtools/panels/dev_cert_catalog_editor.py` (which
rewrote the source file) and shipping a new build. This seeds the real
catalog with the exact same data, preserving every existing numeric id
unchanged: personnel records embed certifications by `cert_type_id`
reference, and `modules/operations/taskings/repository.py` resolves a
handful of ids to CAPF109 codes, so these ids must not shift.

Existing `certification_types` documents (130 on at least one install, per
Design Documents/legacycode.md) use an unrelated, independently-numbered
id scheme from an older, different certification list and are not read by
any current code path — this migration does not touch or merge them; run
`clear_legacy_certification_types` first (or pass --replace) if you want
them gone rather than just shadowed by this seed.

Run with SARAPP_MONGO_URI set in the environment, against whichever
database get_master_db() resolves to (a local catalog by default, or the
central catalog with SARAPP_MASTER_DB_NAME=sarapp_central_master):

    python -m sarapp_db.migrations.seed_certification_types_from_hardcoded_catalog
    python -m sarapp_db.migrations.seed_certification_types_from_hardcoded_catalog --dry-run
    python -m sarapp_db.migrations.seed_certification_types_from_hardcoded_catalog --replace
"""
from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete every existing certification_types document first, instead of leaving unrelated legacy rows in place.",
    )
    args = parser.parse_args()

    from modules.personnel.models.cert_catalog import CATALOG

    col = get_master_db()[MasterCollections.CERTIFICATION_TYPES]

    if args.replace:
        existing_count = col.count_documents({})
        log.info("--replace: would delete %d existing document(s)%s", existing_count, " (dry run)" if args.dry_run else "")
        if not args.dry_run:
            col.delete_many({})

    now = _utcnow()
    inserted = 0
    skipped = 0
    for ct in CATALOG:
        if col.find_one({"id": ct.id}):
            skipped += 1
            log.warning("Skipping id=%d (%s): already present.", ct.id, ct.code)
            continue
        doc = {
            "id": ct.id,
            "code": ct.code,
            "name": ct.name,
            "category": ct.category,
            "issuing_org": ct.issuing_org,
            "parent_id": ct.parent_id,
            "tags": list(ct.tags),
            "is_medical": ct.is_medical,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        if not args.dry_run:
            col.insert_one(doc)
        inserted += 1

    log.info(
        "Seed complete%s: %d inserted, %d skipped (already present).",
        " (dry run)" if args.dry_run else "",
        inserted,
        skipped,
    )


if __name__ == "__main__":
    main()
