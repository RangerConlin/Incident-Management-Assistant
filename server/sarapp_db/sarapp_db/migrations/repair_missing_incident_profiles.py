"""
One-time migration: backfill missing incident profile documents.

Some incident databases were created without an `incident_profile` document,
which leaves the incident overview panel unable to load or save the record.
The canonical fix is to restore the missing profile document from the system
incident registry and then keep the application code on the canonical profile
shape only.

What this script does:
  1. Enumerate all sarapp_incident_* databases.
  2. For each incident database that has no `incident_profile` document, look up
     the matching registry record in `sarapp_system.incidents`.
  3. Insert a canonical incident profile document derived from the registry
     record.

Run with SARAPP_MONGO_URI set in the environment.

    python -m sarapp_db.migrations.repair_missing_incident_profiles

Add --dry-run to preview changes without writing anything.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

from sarapp_db.mongo.collection_names import IncidentCollections, SystemCollections
from sarapp_db.mongo.database_manager import get_client
from sarapp_db.mongo.repository import BaseRepository

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


class SystemIncidentsRepository(BaseRepository):
    collection_name = SystemCollections.INCIDENTS
    soft_deletes = False


class IncidentProfileRepository(BaseRepository):
    collection_name = IncidentCollections.INCIDENT_PROFILE
    soft_deletes = False


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _incident_key(db_name: str) -> str:
    prefix = "sarapp_incident_"
    return db_name[len(prefix):] if db_name.startswith(prefix) else db_name


def _registry_matches(incident_doc: dict[str, Any], incident_key: str) -> bool:
    candidates = {
        str(incident_doc.get("incident_id") or "").strip(),
        str(incident_doc.get("id") or "").strip(),
        str(incident_doc.get("number") or "").strip(),
    }
    return incident_key in candidates


def _build_profile_document(incident_key: str, incident_doc: dict[str, Any]) -> dict[str, Any]:
    now = incident_doc.get("created_at") or incident_doc.get("updated_at") or _utcnow_iso()
    location = str(incident_doc.get("icp_location") or incident_doc.get("icp_address") or "").strip()
    profile: dict[str, Any] = {
        "incident_id": incident_key,
        "name": str(incident_doc.get("name") or incident_doc.get("number") or incident_key).strip(),
        "incident_number": str(incident_doc.get("number") or incident_key).strip(),
        "incident_type": str(incident_doc.get("type") or incident_doc.get("incident_type") or "").strip(),
        "icp_address": location,
        "icp_facility_id": incident_doc.get("icp_facility_id") or None,
        "latitude": incident_doc.get("latitude"),
        "longitude": incident_doc.get("longitude"),
        "start_time": incident_doc.get("start_time") or now,
        "end_time": incident_doc.get("end_time") or None,
        "status": str(incident_doc.get("status") or "active").strip().lower() or "active",
        "is_training": bool(incident_doc.get("is_training", False)),
    }
    description = str(incident_doc.get("description") or "").strip()
    if description:
        profile["description"] = description
    return profile


def _migrate_incident(client, db_name: str, dry_run: bool) -> dict[str, int]:
    db = client[db_name]
    profile_repo = IncidentProfileRepository(db)
    system_repo = SystemIncidentsRepository(client["sarapp_system"])
    incident_key = _incident_key(db_name)
    stats = {
        "dbs_scanned": 1,
        "profiles_found": 0,
        "profiles_created": 0,
        "registry_matches": 0,
        "registry_missing": 0,
        "errors": 0,
    }

    existing = profile_repo.find_one({"incident_id": incident_key})
    if existing:
        stats["profiles_found"] = 1
        return stats

    registry_docs = system_repo.find_many({})
    registry_doc = next((doc for doc in registry_docs if _registry_matches(doc, incident_key)), None)
    if registry_doc is None:
        log.warning("[%s] no matching system incident record found; leaving profile missing", db_name)
        stats["registry_missing"] = 1
        return stats

    stats["registry_matches"] = 1
    profile_doc = _build_profile_document(incident_key, registry_doc)
    log.info("[%s] creating missing incident_profile for incident '%s'", db_name, incident_key)
    if not dry_run:
        profile_repo.insert_one(profile_doc)
    stats["profiles_created"] = 1
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair missing incident_profile documents.")
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
        "profiles_found": 0,
        "profiles_created": 0,
        "registry_matches": 0,
        "registry_missing": 0,
        "errors": 0,
    }
    for db_name in incident_dbs:
        try:
            stats = _migrate_incident(client, db_name, dry_run=args.dry_run)
            for key, value in stats.items():
                totals[key] += value
        except Exception as exc:
            totals["errors"] += 1
            log.error("[%s] migration failed: %s", db_name, exc)

    log.info("Migration complete%s", " (dry run)" if args.dry_run else "")
    log.info("Databases scanned:   %d", totals["dbs_scanned"])
    log.info("Profiles found:      %d", totals["profiles_found"])
    log.info("Profiles created:    %d", totals["profiles_created"])
    log.info("Registry matches:    %d", totals["registry_matches"])
    log.info("Registry missing:    %d", totals["registry_missing"])
    log.info("Errors:              %d", totals["errors"])

    if totals["errors"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
