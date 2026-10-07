"""One-off export: dump this server's real local-catalog (sarapp_master)
data to CSV, one file per master collection, for seeding the central
catalog (sarapp_central_master) once it exists.

This is deliberately separate from `data/master_catalog_seed/` (that
directory holds generic starter templates for a brand-new agency with no
data yet — e.g. "Fire Department (Standard)" rank structures — not this
installation's real data). Output goes to
`data/cloud_catalog_migration_seed/` instead, so it never collides with or
overwrites those templates.

Run with ``SARAPP_MONGO_URI`` set in the environment, from the repo root::

    python scripts/export_master_catalog_seed_csvs.py
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "data" / "db"))

import os

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from sarapp_db.mongo.database_manager import DB_MASTER, get_client  # noqa: E402

OUT_DIR = _REPO_ROOT / "data" / "cloud_catalog_migration_seed"

# Collections deliberately excluded:
# - users/user_sessions/client_connections/push_tokens: local-catalog-only
#   by design (session/device state, not agency catalog data) — see
#   mongodb_schema_decisions.md's terminology section.
# - organization_audit_log/rank_structure_audit_log: historical change
#   logs, not catalog data a fresh central catalog should inherit.
# - personnel_certifications: legacy, empty on a cut-over install — see
#   Design Documents/legacycode.md.
_EXCLUDED_COLLECTIONS = {
    "users",
    "user_sessions",
    "client_connections",
    "push_tokens",
    "organization_audit_log",
    "rank_structure_audit_log",
    "personnel_certifications",
}

# Fields dropped from the generic raw-dump path: Mongo's own _id, and any
# purely-local sequential id this installation assigned (a fresh central
# catalog mints its own on import, whether that's person_record_master-style
# or a plain int_id) — none of these mean anything on a different server.
_GENERIC_DROP_FIELDS = {"_id", "int_id"}
_GENERIC_DROP_SUFFIXES = ("_record", "_record_master")


def _json_cell(value):
    if value in (None, ""):
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _write_csv(filename: str, fieldnames: list[str], rows: list[dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / filename
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print(f"wrote {path} ({len(rows)} rows)")


# ---------------------------------------------------------------------------
# Curated exports — collections with an established, human-readable column
# format already in use elsewhere (the dashboard's own export/import, or the
# existing data/master_catalog_seed/ templates' own header convention).
# ---------------------------------------------------------------------------

def _export_personnel(db) -> None:
    from modules.personnel.catalog_io import PERSONNEL_FIELDS, certification_catalogs, personnel_export_row

    _, catalog_by_id = certification_catalogs()
    docs = list(db["personnel"].find({}))
    rows = [personnel_export_row(d, catalog_by_id) for d in docs]
    _write_csv("personnel.csv", [f.key for f in PERSONNEL_FIELDS], rows)


def _export_equipment(db) -> None:
    from modules.logistics.equipment_catalog_io import FIELDS

    keys = [f.key for f in FIELDS]
    docs = list(db["equipment"].find({}))
    rows = [{k: d.get(k, "") for k in keys} for d in docs]
    _write_csv("equipment.csv", keys, rows)


def _export_vehicles(db) -> None:
    keys = [
        "vehicle_id", "vin", "license_plate", "year", "make", "model",
        "capacity", "type_id", "status_id", "organization", "resource_type_id", "tags",
    ]
    docs = list(db["vehicles"].find({}))
    rows = [{k: d.get(k, "") for k in keys} for d in docs]
    _write_csv("vehicles.csv", keys, rows)


def _export_aircraft(db) -> None:
    keys = [
        "aircraft_id", "callsign", "type", "make", "model", "base", "current_location",
        "status", "organization", "fuel_type", "range_nm", "endurance_hr", "cruise_kt",
        "crew_min", "crew_max", "adsb_hex", "radio_vhf_air", "radio_vhf_sar", "radio_uhf",
        "cap_hoist", "cap_nvg", "cap_flir", "cap_ifr", "payload_kg", "med_config",
        "serial_number", "year", "owner_operator", "registration_exp", "inspection_due",
        "last_100hr", "next_100hr", "notes",
    ]
    docs = list(db["aircraft"].find({}))
    rows = [{k: d.get(k, "") for k in keys} for d in docs]
    _write_csv("aircraft.csv", keys, rows)


def _org_type_name(db, type_id) -> str:
    if type_id is None:
        return ""
    doc = db["organization_types"].find_one({"int_id": type_id})
    return doc.get("name", "") if doc else ""


def _export_organization_types(db) -> None:
    keys = ["Name", "Description", "Sort Order", "Active"]
    docs = list(db["organization_types"].find({}).sort("name", 1))
    rows = [
        {
            "Name": d.get("name", ""),
            "Description": d.get("description") or "",
            "Sort Order": d.get("sort_order", 0),
            "Active": "Yes" if d.get("is_active", True) else "No",
        }
        for d in docs
    ]
    _write_csv("organization_types.csv", keys, rows)


def _export_rank_structures(db) -> None:
    keys = [
        "Name", "Description", "Organization Type ID", "Organization Type Name",
        "Template", "System Template", "Sort Order", "Active",
    ]
    docs = list(db["rank_structures"].find({}).sort("name", 1))
    rows = [
        {
            "Name": d.get("name", ""),
            "Description": d.get("description") or "",
            "Organization Type ID": "",
            "Organization Type Name": _org_type_name(db, d.get("organization_type_id")),
            "Template": "Yes" if d.get("is_template") else "",
            "System Template": "Yes" if d.get("is_system_template") else "",
            "Sort Order": d.get("sort_order", 0),
            "Active": "Yes" if d.get("is_active", True) else "No",
        }
        for d in docs
    ]
    _write_csv("rank_structures.csv", keys, rows)


def _export_ranks(db) -> None:
    keys = ["Rank Structure ID", "Rank Structure Name", "Rank Code", "Rank Name", "Short Display", "Sort Order", "Active"]
    structures_by_id = {d["int_id"]: d for d in db["rank_structures"].find({})}
    docs = list(db["ranks"].find({}).sort([("rank_structure_id", 1), ("sort_order", 1)]))
    rows = []
    for d in docs:
        structure = structures_by_id.get(d.get("rank_structure_id")) or {}
        rows.append({
            "Rank Structure ID": "",
            "Rank Structure Name": structure.get("name", ""),
            "Rank Code": d.get("rank_code", ""),
            "Rank Name": d.get("rank_name", ""),
            "Short Display": d.get("short_display", ""),
            "Sort Order": d.get("sort_order", 0),
            "Active": "Yes" if d.get("is_active", True) else "No",
        })
    _write_csv("ranks.csv", keys, rows)


def _export_organizations(db) -> None:
    keys = [
        "Name", "Short Name", "Call Sign", "Organization Type", "Parent Organization",
        "Address", "Latitude", "Longitude", "Sort Order", "Active", "Notes",
    ]
    orgs_by_id = {d["int_id"]: d for d in db["organizations"].find({})}
    docs = list(db["organizations"].find({}).sort("name", 1))
    rows = []
    for d in docs:
        parent = orgs_by_id.get(d.get("parent_organization_id") or d.get("parent_id")) or {}
        rows.append({
            "Name": d.get("name", ""),
            "Short Name": d.get("short_name", "") or "",
            "Call Sign": d.get("call_sign", "") or "",
            "Organization Type": _org_type_name(db, d.get("organization_type_id") or d.get("org_type_id")),
            "Parent Organization": parent.get("name", ""),
            "Address": d.get("address", "") or "",
            "Latitude": d.get("latitude", "") or "",
            "Longitude": d.get("longitude", "") or "",
            "Sort Order": d.get("sort_order", 0),
            "Active": "Yes" if d.get("is_active", True) else "No",
            "Notes": d.get("notes", "") or "",
        })
    _write_csv("organizations.csv", keys, rows)


_CURATED_EXPORTERS = {
    "personnel": _export_personnel,
    "equipment": _export_equipment,
    "vehicles": _export_vehicles,
    "aircraft": _export_aircraft,
    "organization_types": _export_organization_types,
    "rank_structures": _export_rank_structures,
    "ranks": _export_ranks,
    "organizations": _export_organizations,
}


# ---------------------------------------------------------------------------
# Generic raw-dump path — every other master collection with real data and
# no established column format yet. One column per field actually present
# across the collection's documents; nested/list values are JSON-encoded
# into the cell rather than dropped, so no data is lost even though it
# isn't flattened prettily. A future import feature for these collections
# can read the JSON back out.
# ---------------------------------------------------------------------------

def _export_generic(db, collection: str) -> None:
    docs = list(db[collection].find({}))
    if not docs:
        print(f"skip {collection} (empty)")
        return
    fieldnames: list[str] = []
    seen = set()
    for doc in docs:
        for key in doc.keys():
            if key in _GENERIC_DROP_FIELDS or key.endswith(_GENERIC_DROP_SUFFIXES):
                continue
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    rows = [{k: _json_cell(doc.get(k, "")) for k in fieldnames} for doc in docs]
    _write_csv(f"{collection}.csv", fieldnames, rows)


def main() -> None:
    client = get_client()
    db = client[DB_MASTER]
    all_collections = set(db.list_collection_names())

    for collection, exporter in _CURATED_EXPORTERS.items():
        if collection in all_collections and db[collection].count_documents({}) > 0:
            exporter(db)
        else:
            print(f"skip {collection} (empty or missing)")

    remaining = sorted(all_collections - set(_CURATED_EXPORTERS) - _EXCLUDED_COLLECTIONS)
    for collection in remaining:
        _export_generic(db, collection)


if __name__ == "__main__":
    main()
