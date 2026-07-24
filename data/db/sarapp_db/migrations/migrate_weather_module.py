"""
One-time migration: old flat `weather_data` "config" doc -> `weather_config`.

The legacy weather module stored a single blob per incident in `weather_data`
(key="config") with flat latitude/longitude/icao_codes/location_presets
fields and a cached `weather_payload`. The rebuilt weather module stores a
proper `locations` array (with per-location coordinates/ICAO codes) and
Go/No-Go `thresholds` in a new `weather_config` collection.

What this script does:
  1. Enumerate all sarapp_incident_* databases.
  2. For each incident with a legacy weather_data "config" document, build a
     `locations` array: one entry per `location_presets` item if present,
     otherwise a single default location from the flat latitude/longitude/
     icao_codes fields.
  3. Insert a `weather_config` document with default (not fabricated
     per-incident) Go/No-Go thresholds, since the legacy schema never had
     threshold data of any kind.
  4. Leave the old `weather_data` collection untouched (inert) — it is not
     deleted by this script; run a separate cleanup pass after verifying the
     new schema in production for a release cycle.

No history backfill is performed: the legacy system recorded no historical
readings, so `weather_history` starts empty for every incident.

Run with SARAPP_MONGO_URI set in the environment.

    python -m sarapp_db.migrations.migrate_weather_module

Add --dry-run to preview changes without writing anything. Safe to re-run
(idempotent) — incidents that already have a weather_config document are
skipped.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import uuid
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

_DEFAULT_THRESHOLDS: dict[str, Any] = {
    "ground": {
        "wind_gust_marginal_mph": 20.0,
        "wind_gust_nogo_mph": 30.0,
        "visibility_marginal_mi": 3.0,
        "visibility_nogo_mi": 1.0,
        "ceiling_marginal_ft": 1500.0,
        "ceiling_nogo_ft": 500.0,
        "heat_index_marginal_f": 90.0,
        "heat_index_nogo_f": 103.0,
    },
    "aviation": {
        "wind_gust_marginal_kt": 15.0,
        "wind_gust_nogo_kt": 25.0,
        "visibility_marginal_sm": 3.0,
        "visibility_nogo_sm": 1.0,
        "ceiling_marginal_ft_agl": 1000.0,
        "ceiling_nogo_ft_agl": 300.0,
        "crosswind_marginal_kt": 15.0,
        "crosswind_nogo_kt": 25.0,
    },
}


def _as_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _location_from_preset(preset: dict[str, Any], *, is_default: bool) -> dict[str, Any]:
    icao_codes = preset.get("icao_codes")
    if not icao_codes and preset.get("icao"):
        icao_codes = [preset["icao"]]
    return {
        "location_id": uuid.uuid4().hex,
        "label": str(preset.get("label") or preset.get("name") or "Migrated location"),
        "latitude": _as_float(preset.get("latitude")),
        "longitude": _as_float(preset.get("longitude")),
        "icao_codes": list(icao_codes or []),
        "is_default": is_default,
        "source": "manual",
        "source_ref_id": None,
        "created_at": None,
        "created_by": "migration",
    }


def _build_locations(legacy: dict[str, Any]) -> list[dict[str, Any]]:
    presets = legacy.get("location_presets") or []
    active_preset = str(legacy.get("active_location_preset") or "")
    if presets:
        locations = []
        for preset in presets:
            label = str(preset.get("label") or preset.get("name") or "")
            is_default = bool(label and label == active_preset) or (not active_preset and preset is presets[0])
            locations.append(_location_from_preset(preset, is_default=is_default))
        if not any(loc["is_default"] for loc in locations):
            locations[0]["is_default"] = True
        return locations

    lat = _as_float(legacy.get("latitude"))
    lon = _as_float(legacy.get("longitude"))
    icao_codes = legacy.get("icao_codes") or []
    if lat is None and lon is None and not icao_codes:
        return []
    return [
        {
            "location_id": uuid.uuid4().hex,
            "label": "Migrated default location",
            "latitude": lat,
            "longitude": lon,
            "icao_codes": list(icao_codes),
            "is_default": True,
            "source": "manual",
            "source_ref_id": None,
            "created_at": None,
            "created_by": "migration",
        }
    ]


def _migrate_incident(db, incident_id: str, dry_run: bool) -> dict[str, int]:
    stats = {"legacy_found": 0, "already_migrated": 0, "configs_created": 0, "locations_created": 0}

    weather_config_col = db["weather_config"]
    if weather_config_col.find_one({"incident_id": incident_id}):
        stats["already_migrated"] += 1
        return stats

    legacy = db["weather_data"].find_one({"incident_id": incident_id, "key": "config"})
    if not legacy:
        return stats

    stats["legacy_found"] += 1
    locations = _build_locations(legacy)
    stats["locations_created"] = len(locations)

    polling_minutes = legacy.get("polling_minutes")
    try:
        polling_minutes = max(1, int(polling_minutes)) if polling_minutes else 10
    except (TypeError, ValueError):
        polling_minutes = 10

    config_doc = {
        "_id": uuid.uuid4().hex,
        "incident_id": incident_id,
        "polling_minutes": polling_minutes,
        "locations": locations,
        "thresholds": _DEFAULT_THRESHOLDS,
        "updated_at": None,
        "updated_by": "migration",
        "deleted": False,
    }

    if not dry_run:
        weather_config_col.insert_one(config_doc)
    stats["configs_created"] += 1
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate legacy weather_data config docs to weather_config.")
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

    totals = {"legacy_found": 0, "already_migrated": 0, "configs_created": 0, "locations_created": 0}
    for db_name in incident_dbs:
        incident_id = db_name[len("sarapp_incident_"):]
        log.info("Processing %s ...", db_name)
        stats = _migrate_incident(client[db_name], incident_id, dry_run=args.dry_run)
        for key, value in stats.items():
            totals[key] += value

    client.close()
    log.info("Migration complete%s", " (dry run)" if args.dry_run else "")
    log.info("Legacy configs found:  %d", totals["legacy_found"])
    log.info("Already migrated:      %d", totals["already_migrated"])
    log.info("weather_config created: %d", totals["configs_created"])
    log.info("Locations created:     %d", totals["locations_created"])
    log.info("Note: weather_history starts empty for every incident — no history backfill is possible.")


if __name__ == "__main__":
    main()
