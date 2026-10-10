"""One-time seed: populate the `qualification_types` collection from the
previously-hardcoded `modules/personnel/models/validation_profiles.py`
PROFILES tuple.

Before this migration, `PROFILES` was a Python tuple of `QualProfile`
dataclasses, editable only by changing source code and shipping a new
build. This seeds the real catalog with the exact same data (code, name,
any_tags, all_tags, min_level). Unlike the certification catalog, these
profiles have no existing numeric id to preserve — `code` is the only
identity that matters to callers (`cert_api.qualifications_met`), so ids
are freshly minted in `PROFILES` order.

Run with SARAPP_MONGO_URI set in the environment, against whichever
database get_master_db() resolves to (a local catalog by default, or the
central catalog with SARAPP_MASTER_DB_NAME=sarapp_central_master):

    python -m sarapp_db.migrations.seed_qualification_types_from_hardcoded_profiles
    python -m sarapp_db.migrations.seed_qualification_types_from_hardcoded_profiles --dry-run
"""
from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.int_id import next_record_id

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from modules.personnel.models.validation_profiles import PROFILES

    col = get_master_db()[MasterCollections.QUALIFICATION_TYPES]

    now = _utcnow()
    inserted = 0
    skipped = 0
    for profile in PROFILES:
        if col.find_one({"code": profile.code}):
            skipped += 1
            log.warning("Skipping code=%s: already present.", profile.code)
            continue
        doc = {
            "id": next_record_id(col, "id") if not args.dry_run else None,
            "code": profile.code,
            "name": profile.name,
            "any_tags": list(profile.any_tags),
            "all_tags": list(profile.all_tags),
            "min_level": profile.min_level,
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
