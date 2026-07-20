"""
One-time migration: normalize GIS enum storage values.

Some spatial feature documents were written with Python enum string
representations such as ``FeatureType.LANDING_ZONE`` and
``GeometryType.POINT`` instead of their canonical persisted values
(``landing_zone`` and ``POINT`` respectively). The canonical fix is to
rewrite those documents once, then keep application code writing only the
canonical values.

What this script does:
  1. Enumerate all ``sarapp_incident_*`` databases.
  2. Find spatial feature documents whose ``feature_type`` or
     ``geometry_type`` fields are stored as enum repr strings.
  3. Rewrite those fields in place to their canonical enum values.

Run with SARAPP_MONGO_URI set in the environment.

    python -m sarapp_db.migrations.repair_gis_enum_storage

Add --dry-run to preview changes without writing anything.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from enum import Enum

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_client
from sarapp_db.mongo.repository import BaseRepository

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


class SpatialFeaturesRepository(BaseRepository):
    collection_name = IncidentCollections.SPATIAL_FEATURES
    soft_deletes = False


def _normalize_enum_storage(value: object, enum_cls: type[Enum]) -> str | None:
    if not isinstance(value, str):
        return None
    prefix = f"{enum_cls.__name__}."
    if not value.startswith(prefix):
        return None
    member_name = value[len(prefix):]
    try:
        return str(enum_cls[member_name].value)
    except KeyError:
        return None


def _repair_incident_db(client, db_name: str, feature_enum: type[Enum], geometry_enum: type[Enum], dry_run: bool) -> dict[str, int]:
    repo = SpatialFeaturesRepository(client[db_name])
    stats = {
        "dbs_scanned": 1,
        "docs_scanned": 0,
        "docs_changed": 0,
        "feature_type_fixed": 0,
        "geometry_type_fixed": 0,
        "errors": 0,
    }

    docs = repo.find_many({})
    for doc in docs:
        stats["docs_scanned"] += 1
        updates: dict[str, str] = {}

        feature_type = _normalize_enum_storage(doc.get("feature_type"), feature_enum)
        if feature_type is not None:
            updates["feature_type"] = feature_type
            stats["feature_type_fixed"] += 1

        geometry_type = _normalize_enum_storage(doc.get("geometry_type"), geometry_enum)
        if geometry_type is not None:
            updates["geometry_type"] = geometry_type
            stats["geometry_type_fixed"] += 1

        if not updates:
            continue

        stats["docs_changed"] += 1
        log.info("[%s] normalizing spatial feature %s with %s", db_name, doc.get("int_id"), sorted(updates))
        if not dry_run:
            repo.update_one(doc["_id"], updates)

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair GIS enum storage values.")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing anything.")
    args = parser.parse_args()

    mongo_uri = os.environ.get("SARAPP_MONGO_URI")
    if not mongo_uri:
        log.error("SARAPP_MONGO_URI environment variable is not set.")
        sys.exit(1)

    try:
        client = get_client()
    except Exception as exc:
        log.error("Unable to connect to MongoDB: %s", exc)
        sys.exit(1)

    from modules.gis.models.feature_types import FeatureType
    from modules.gis.models.geometry_types import GeometryType

    if args.dry_run:
        log.info("DRY RUN — no data will be written.")

    incident_dbs = [
        name for name in client.list_database_names()
        if name.startswith("sarapp_incident_")
    ]
    if not incident_dbs:
        log.info("No incident databases found. Nothing to do.")
        return

    totals = {
        "dbs_scanned": 0,
        "docs_scanned": 0,
        "docs_changed": 0,
        "feature_type_fixed": 0,
        "geometry_type_fixed": 0,
        "errors": 0,
    }

    for db_name in incident_dbs:
        try:
            stats = _repair_incident_db(
                client,
                db_name,
                feature_enum=FeatureType,
                geometry_enum=GeometryType,
                dry_run=args.dry_run,
            )
            for key, value in stats.items():
                totals[key] += value
        except Exception as exc:
            totals["errors"] += 1
            log.error("[%s] migration failed: %s", db_name, exc)

    log.info("Migration complete%s", " (dry run)" if args.dry_run else "")
    log.info("Databases scanned:    %d", totals["dbs_scanned"])
    log.info("Documents scanned:    %d", totals["docs_scanned"])
    log.info("Documents changed:    %d", totals["docs_changed"])
    log.info("Feature types fixed:  %d", totals["feature_type_fixed"])
    log.info("Geometry types fixed: %d", totals["geometry_type_fixed"])
    log.info("Errors:               %d", totals["errors"])

    if totals["errors"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
