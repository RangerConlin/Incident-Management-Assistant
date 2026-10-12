"""
One-time migration: move incident ICP source-of-truth to facilities.

The legacy incident profile stored `icp_location` plus latitude/longitude directly.
The facilities module now owns the canonical ICP record, and incident profiles should
reference the selected facility via `icp_facility_id`.

What this script does:
  1. Enumerate all sarapp_incident_* databases.
  2. For each incident profile with legacy ICP data, try to find an existing facility
     in that incident that matches by facility id, name, address, geocoded address,
     or coordinates.
  3. If a match is found, write `icp_facility_id` back to the incident profile and
     normalize the stored ICP address/coordinates to the facility values.
  4. If no match is found but the profile has usable legacy ICP data, create a
     command-post facility from the existing incident data and link the profile to it.

Run with SARAPP_MONGO_URI set in the environment.

    python -m sarapp_db.migrations.migrate_icp_location_to_facility

Add --dry-run to preview changes without writing anything.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import uuid
from dataclasses import dataclass
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


@dataclass(slots=True)
class LegacyIcp:
    address: str
    latitude: float
    longitude: float


def _as_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _legacy_icp(profile: dict[str, Any]) -> LegacyIcp | None:
    address = str(profile.get("icp_location") or profile.get("icp_address") or "").strip()
    lat = _as_float(profile.get("latitude"))
    lon = _as_float(profile.get("longitude"))
    if not address or lat is None or lon is None:
        return None
    return LegacyIcp(address=address, latitude=lat, longitude=lon)


def _coord_key(lat: float, lon: float) -> tuple[float, float]:
    return (round(lat, 6), round(lon, 6))


def _match_facility(facilities: list[dict[str, Any]], legacy: LegacyIcp) -> dict[str, Any] | None:
    legacy_key = _coord_key(legacy.latitude, legacy.longitude)
    legacy_text = legacy.address.strip().lower()
    for facility in facilities:
        if facility.get("deleted"):
            continue
        if str(facility.get("id") or "") and str(facility.get("id")) == str(facility.get("_id") or ""):
            return facility
        facility_texts = {
            str(facility.get("name") or "").strip().lower(),
            str(facility.get("address") or "").strip().lower(),
            str(facility.get("geocoded_address") or "").strip().lower(),
        }
        if legacy_text and legacy_text in facility_texts:
            return facility
        lat = _as_float(facility.get("latitude"))
        lon = _as_float(facility.get("longitude"))
        if lat is not None and lon is not None and _coord_key(lat, lon) == legacy_key:
            return facility
    return None


def _migrate_incident(client, db_name: str, dry_run: bool) -> dict[str, int]:
    db = client[db_name]
    profile = db["incident_profile"].find_one({})
    if not profile:
        return {"profiles_scanned": 0, "profiles_updated": 0, "facilities_created": 0, "matches_found": 0, "errors": 0}

    facilities_col = db["facilities"]
    incident_id = str(profile.get("incident_id") or profile.get("_id") or "")
    legacy = _legacy_icp(profile)
    stats = {"profiles_scanned": 1, "profiles_updated": 0, "facilities_created": 0, "matches_found": 0, "errors": 0}
    if not legacy:
        return stats

    facilities = list(facilities_col.find({"incident_id": incident_id}))
    match = _match_facility(facilities, legacy)
    update: dict[str, Any] = {}

    if match:
        stats["matches_found"] += 1
        update = {
            "icp_facility_id": str(match.get("id") or match.get("_id") or ""),
            "icp_address": str(match.get("name") or match.get("address") or legacy.address),
            "latitude": match.get("latitude"),
            "longitude": match.get("longitude"),
            "icp_location": str(match.get("name") or match.get("address") or legacy.address),
        }
    else:
        facility_doc = {
            "_id": uuid.uuid4().hex,
            "id": uuid.uuid4().hex,
            "incident_id": incident_id,
            "name": legacy.address,
            "facility_type": "command_post",
            "status": "active",
            "address": legacy.address,
            "latitude": legacy.latitude,
            "longitude": legacy.longitude,
            "geocoded_address": legacy.address,
            "manager_personnel_id": "",
            "manager_name": "",
            "contact_name": "",
            "contact_phone": "",
            "notes": "Created by ICP migration.",
            "function_tags": ["ICP"],
            "served_sections": [],
            "is_primary": True,
            "metadata": {},
        }
        stats["facilities_created"] += 1
        update = {
            "icp_facility_id": facility_doc["id"],
            "icp_address": legacy.address,
            "latitude": legacy.latitude,
            "longitude": legacy.longitude,
            "icp_location": legacy.address,
        }
        if not dry_run:
            facilities_col.insert_one(facility_doc)

    if not update:
        return stats

    if not dry_run:
        db["incident_profile"].update_one({"_id": profile["_id"]}, {"$set": update})
        sys_incident = db["incidents"].find_one({"incident_id": incident_id}) or db["incidents"].find_one({"_id": incident_id})
        if sys_incident:
            db["incidents"].update_one(
                {"_id": sys_incident["_id"]},
                {
                    "$set": {
                        "icp_location": update["icp_address"],
                        "icp_facility_id": update["icp_facility_id"],
                    }
                },
            )

    stats["profiles_updated"] += 1
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate incident ICP location to facilities.")
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

    incident_dbs = [name for name in client.list_database_names() if name.startswith("sarapp_incident_")]
    if not incident_dbs:
        log.info("No incident databases found. Nothing to do.")
        return

    totals = {"profiles_scanned": 0, "profiles_updated": 0, "facilities_created": 0, "matches_found": 0, "errors": 0}
    for db_name in incident_dbs:
        log.info("Processing %s ...", db_name)
        stats = _migrate_incident(client, db_name, dry_run=args.dry_run)
        for key, value in stats.items():
            totals[key] += value

    client.close()
    log.info("Migration complete%s", " (dry run)" if args.dry_run else "")
    log.info("Profiles scanned:   %d", totals["profiles_scanned"])
    log.info("Profiles updated:   %d", totals["profiles_updated"])
    log.info("Facilities created: %d", totals["facilities_created"])
    log.info("Matches found:      %d", totals["matches_found"])


if __name__ == "__main__":
    main()
