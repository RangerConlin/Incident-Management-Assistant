"""One-time cleanup: drop the `is_medical` field from `certification_types`
documents.

The field is redundant now that certification types are tagged against the
qualification catalog (`data/db/sarapp_db/api/routers/qualification_types.py`)
— a cert's "medical-ness" is expressed by carrying a tag a medical
qualification (e.g. `MEDICAL_PROVIDER`) actually looks for (typically
`MEDIC`), not by a separate boolean nothing in the app ever read for
filtering/logic. The router, `cert_api.py`, and both UIs (desktop
Certifications tab, central dashboard) no longer read or write this field;
this just clears it off existing documents so the canonical shape has no
dead field left over.

Run with SARAPP_MONGO_URI set in the environment, against whichever
database get_master_db() resolves to (a local catalog by default, or the
central catalog with SARAPP_MASTER_DB_NAME=sarapp_central_master):

    python -m sarapp_db.migrations.remove_is_medical_from_certification_types
    python -m sarapp_db.migrations.remove_is_medical_from_certification_types --dry-run
"""
from __future__ import annotations

import argparse
import logging

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    col = get_master_db()[MasterCollections.CERTIFICATION_TYPES]
    matched = col.count_documents({"is_medical": {"$exists": True}})
    log.info(
        "%d document(s) have is_medical set%s.",
        matched,
        " (dry run, not modifying)" if args.dry_run else "",
    )
    if matched and not args.dry_run:
        result = col.update_many({"is_medical": {"$exists": True}}, {"$unset": {"is_medical": ""}})
        log.info("Cleared is_medical from %d document(s).", result.modified_count)


if __name__ == "__main__":
    main()
