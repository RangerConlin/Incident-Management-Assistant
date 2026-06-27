"""
One-time seed script: reads from data/master.db (SQLite) and writes to
sarapp_master (MongoDB).

Rules:
    - Never modifies master.db or any SQLite data.
    - Skips documents that already exist in MongoDB (idempotent by SQLite id).
    - Prints a clear per-collection summary.
    - Does not create fake or demo data — only migrates what is already in master.db.

Usage:
    python data/db/seed_master_from_sqlite.py

With a custom MongoDB URI:
    SARAPP_MONGO_URI=mongodb://... python data/db/seed_master_from_sqlite.py
"""

from __future__ import annotations

import glob
import json
import os
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Any

# Allow running from the repo root.
_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from sarapp_db.mongo.database_manager import DatabaseManager
from sarapp_db.mongo.collection_names import MasterCollections

_SQLITE_PATH = _repo_root / "data" / "master.db"


def _connect_sqlite() -> sqlite3.Connection:
    if not _SQLITE_PATH.exists():
        print(f"ERROR: master.db not found at {_SQLITE_PATH}")
        sys.exit(1)
    conn = sqlite3.connect(str(_SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _new_id() -> str:
    return str(uuid.uuid4())


def _seed_collection(col, docs: list[dict], id_field: str = "_id") -> tuple[int, int]:
    """
    Insert documents that don't already exist, keyed on id_field.
    Returns (inserted, skipped).
    """
    inserted = 0
    skipped = 0
    for doc in docs:
        if col.find_one({id_field: doc[id_field]}) is not None:
            skipped += 1
            continue
        col.insert_one(doc)
        inserted += 1
    return inserted, skipped


def _report(name: str, inserted: int, skipped: int) -> None:
    print(f"  {name:<30} {inserted:>4} inserted   {skipped:>4} skipped")


# ---------------------------------------------------------------------------
# Per-table migration functions
# ---------------------------------------------------------------------------


def reconcile_aircraft_collection(master_db) -> None:
    """
    Normalize pre-existing aircraft documents into the current API shape.

    Older data may already exist in two parallel forms:
      - current API docs keyed by int_id
      - legacy seed docs keyed by aircraft_id

    This routine merges useful legacy fields into the current doc, deletes the
    duplicate legacy row, and backfills aircraft_id on surviving API docs so the
    unique aircraft_id index can be created cleanly.
    """
    col = master_db[MasterCollections.AIRCRAFT]
    docs = list(col.find({}))
    if not docs:
        return

    current_by_tail = {
        str(doc.get("tail_number") or "").strip().upper(): doc
        for doc in docs
        if doc.get("int_id") is not None and str(doc.get("tail_number") or "").strip()
    }

    merged = deleted = backfilled = 0

    for legacy in docs:
        if legacy.get("int_id") is not None:
            continue

        tail = str(legacy.get("tail_number") or "").strip().upper()
        if not tail:
            continue

        current = current_by_tail.get(tail)
        if current is None or current["_id"] == legacy["_id"]:
            continue

        updates: dict[str, Any] = {}
        legacy_aircraft_id = str(legacy.get("aircraft_id") or "").strip()
        if legacy_aircraft_id and not current.get("aircraft_id"):
            updates["aircraft_id"] = legacy_aircraft_id
        if legacy.get("base_location") and not current.get("base"):
            updates["base"] = legacy["base_location"]
        if legacy.get("make_model") and not current.get("model"):
            updates["model"] = legacy["make_model"]
        if legacy.get("make_model") and not current.get("make_model"):
            updates["make_model"] = legacy["make_model"]
        if legacy.get("capacity") is not None and current.get("capacity") in (None, ""):
            updates["capacity"] = legacy["capacity"]
        if legacy.get("capabilities") and not current.get("capabilities"):
            updates["capabilities"] = legacy["capabilities"]
        if legacy.get("notes") and not current.get("notes"):
            updates["notes"] = legacy["notes"]

        if updates:
            col.update_one({"_id": current["_id"]}, {"$set": updates})
            merged += 1

        col.delete_one({"_id": legacy["_id"]})
        deleted += 1

    for current in col.find({"int_id": {"$exists": True}}):
        aircraft_id = str(current.get("aircraft_id") or "").strip()
        if aircraft_id:
            continue
        col.update_one({"_id": current["_id"]}, {"$set": {"aircraft_id": str(current["int_id"])}})
        backfilled += 1

    if merged or deleted or backfilled:
        print(
            f"  {'aircraft reconcile':<30}"
            f" {merged:>4} merged   {deleted:>4} deleted   {backfilled:>4} backfilled"
        )

def seed_personnel(cur: sqlite3.Cursor, master_db) -> None:
    cur.execute("SELECT * FROM personnel")
    rows = [dict(r) for r in cur.fetchall()]

    # Pull certifications so we can embed them
    cur.execute("""
        SELECT pc.person_id, ct.Code, ct.name, ct.category, pc.level, pc.attachment_url
        FROM personnel_certifications pc
        LEFT JOIN certification_types ct ON ct.id = pc.certification_id
    """)
    certs_by_person: dict[int, list] = {}
    for row in cur.fetchall():
        certs_by_person.setdefault(row["person_id"], []).append({
            "certification_code": row["Code"],
            "certification_name": row["name"],
            "category": row["category"],
            "level": row["level"],
            "attachment_url": row["attachment_url"],
        })

    docs = []
    for r in rows:
        # Skip blank placeholder rows
        if not r.get("name", "").strip():
            continue
        docs.append({
            "_id": _new_id(),
            "personnel_id": str(r["id"]),
            "name": r["name"],
            "rank": r["rank"],
            "callsign": r["callsign"],
            "role": r["role"],
            "phone": r["phone"] or r["contact"],
            "email": r["email"],
            "organization": r["organization"],
            "unit": r["unit"],
            "notes": r["notes"],
            "photo_url": r["photo_url"],
            "emergency_contact_name": r["emergency_contact_name"],
            "emergency_contact_phone": r["emergency_contact_phone"],
            "emergency_contact_relationship": r["emergency_contact_relationship"],
            "status": "available",
            "certifications": certs_by_person.get(r["id"], []),
        })

    col = master_db[MasterCollections.PERSONNEL]
    i, s = _seed_collection(col, docs, id_field="personnel_id")
    _report("personnel", i, s)


def seed_certification_types(cur: sqlite3.Cursor, master_db) -> None:
    cur.execute("SELECT * FROM certification_types")
    rows = [dict(r) for r in cur.fetchall()]

    # Build a lookup of SQLite id -> certification_type_id string so parent
    # references resolve to real IDs rather than copying orphaned integers.
    valid_ids = {r["id"] for r in rows}

    docs = [{
        "_id": _new_id(),
        "certification_type_id": str(r["id"]),
        "code": r["Code"],
        "name": r["name"],
        "description": r["description"],
        "category": r["category"],
        "issuing_organization": r["issuing_organization"],
        # Only set parent if the referenced ID actually exists in this table.
        "parent_certification_id": str(r["parent_certification_id"])
            if r["parent_certification_id"] and r["parent_certification_id"] in valid_ids
            else None,
    } for r in rows]
    col = master_db[MasterCollections.CERTIFICATION_TYPES]
    i, s = _seed_collection(col, docs, id_field="certification_type_id")
    _report("certification_types", i, s)


def seed_vehicles(cur: sqlite3.Cursor, master_db) -> None:
    cur.execute("SELECT * FROM vehicles")
    rows = [dict(r) for r in cur.fetchall()]
    docs = [{
        "_id": _new_id(),
        "vehicle_id": str(r["id"]),
        "vin": r["vin"],
        "license_plate": r["license_plate"],
        "year": r["year"],
        "make": r["make"],
        "model": r["model"],
        "capacity": r["capacity"],
        "type_id": r["type_id"],
        "status_id": r["status_id"] or "Available",
        "tags": r["tags"],
        "organization": r["organization"],
        "resource_type_id": str(r["resource_type_id"]) if r["resource_type_id"] else None,
    } for r in rows]
    col = master_db[MasterCollections.VEHICLES]
    i, s = _seed_collection(col, docs, id_field="vehicle_id")
    _report("vehicles", i, s)


def seed_aircraft(cur: sqlite3.Cursor, master_db) -> None:
    cur.execute("SELECT * FROM aircraft")
    rows = [dict(r) for r in cur.fetchall()]
    col = master_db[MasterCollections.AIRCRAFT]
    inserted = updated = skipped = 0
    for r in rows:
        aircraft_id = str(r["id"])
        doc = {
            "_id": _new_id(),
            "aircraft_id": aircraft_id,
            "tail_number": r["tail_number"],
            "callsign": r["callsign"],
            "aircraft_type": r["type"],
            "make_model": r["make_model"],
            "capacity": r["capacity"],
            "status": r["status"] or "available",
            "base_location": r["base_location"],
            "capabilities": r["capabilities"],
            "notes": r["notes"],
        }

        existing = (
            col.find_one({"aircraft_id": aircraft_id})
            or col.find_one({"int_id": int(r["id"])})
            or col.find_one({"tail_number": r["tail_number"]})
        )
        if existing is None:
            col.insert_one(doc)
            inserted += 1
            continue

        updates: dict[str, Any] = {}
        if not existing.get("aircraft_id"):
            updates["aircraft_id"] = aircraft_id
        if doc["base_location"] and not existing.get("base"):
            updates["base"] = doc["base_location"]
        if doc["make_model"] and not existing.get("model"):
            updates["model"] = doc["make_model"]
        if doc["make_model"] and not existing.get("make_model"):
            updates["make_model"] = doc["make_model"]
        if doc["capacity"] is not None and existing.get("capacity") in (None, ""):
            updates["capacity"] = doc["capacity"]
        if doc["capabilities"] and not existing.get("capabilities"):
            updates["capabilities"] = doc["capabilities"]
        if doc["notes"] and not existing.get("notes"):
            updates["notes"] = doc["notes"]

        if updates:
            col.update_one({"_id": existing["_id"]}, {"$set": updates})
            updated += 1
        else:
            skipped += 1

    _report(f"aircraft ({updated} updated)", inserted, skipped)


def seed_equipment(cur: sqlite3.Cursor, master_db) -> None:
    cur.execute("SELECT * FROM equipment")
    rows = [dict(r) for r in cur.fetchall()]
    docs = [{
        "_id": _new_id(),
        "equipment_id": str(r["id"]),
        "name": r["name"],
        "equipment_type": r["type"],
        "serial_number": r["serial_number"],
        "condition": r["condition"],
        "condition_status": r["condition_status"],
        "notes": r["notes"],
        "resource_type_id": str(r["resource_type_id"]) if r["resource_type_id"] else None,
    } for r in rows]
    col = master_db[MasterCollections.EQUIPMENT]
    i, s = _seed_collection(col, docs, id_field="equipment_id")
    _report("equipment", i, s)


def seed_radio_channels(cur: sqlite3.Cursor, master_db) -> None:
    cur.execute("SELECT * FROM comms_resources")
    rows = [dict(r) for r in cur.fetchall()]
    docs = [{
        "_id": _new_id(),
        "channel_id": str(r["id"]),
        "channel_name": r["alpha_tag"],
        "function": r["function"],
        "freq_rx": r["freq_rx"],
        "rx_tone": r["rx_tone"],
        "freq_tx": r["freq_tx"],
        "tx_tone": r["tx_tone"],
        "system": r["system"],
        "mode": r["mode"],
        "notes": r["notes"],
        "line_a": bool(r["line_a"]),
        "line_c": bool(r["line_c"]),
    } for r in rows]
    col = master_db[MasterCollections.RADIO_CHANNELS]
    i, s = _seed_collection(col, docs, id_field="channel_id")
    _report("radio_channels", i, s)


def seed_hazard_types(cur: sqlite3.Cursor, master_db) -> None:
    cur.execute("SELECT * FROM hazard_types")
    rows = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM hazard_type_aliases")
    aliases_by_id: dict[int, list[str]] = {}
    for r in (dict(x) for x in cur.fetchall()):
        aliases_by_id.setdefault(r["hazard_type_id"], []).append(r["alias"])

    cur.execute("SELECT * FROM hazard_mitigations ORDER BY sort_order")
    mitigations_by_id: dict[int, list[dict]] = {}
    for r in (dict(x) for x in cur.fetchall()):
        mitigations_by_id.setdefault(r["hazard_type_id"], []).append({
            "mitigation_text": r["mitigation_text"],
            "mitigation_category": r.get("mitigation_category") or "",
            "is_default": bool(r.get("is_default", 0)),
            "sort_order": r.get("sort_order") or 0,
        })

    cur.execute("SELECT * FROM hazard_ppe ORDER BY sort_order")
    ppe_by_id: dict[int, list[dict]] = {}
    for r in (dict(x) for x in cur.fetchall()):
        ppe_by_id.setdefault(r["hazard_type_id"], []).append({
            "ppe_text": r["ppe_text"],
            "is_default": bool(r.get("is_default", 0)),
            "sort_order": r.get("sort_order") or 0,
        })

    cur.execute("SELECT * FROM hazard_references")
    references_by_id: dict[int, list[dict]] = {}
    for r in (dict(x) for x in cur.fetchall()):
        references_by_id.setdefault(r["hazard_type_id"], []).append({
            "title": r["title"],
            "url_or_path": r.get("url_or_path") or "",
            "notes": r.get("notes") or "",
        })

    resource_defaults_by_id: dict[int, list[dict]] = {}
    try:
        cur.execute("SELECT * FROM hazard_type_resource_defaults")
        for r in (dict(x) for x in cur.fetchall()):
            resource_defaults_by_id.setdefault(r["hazard_type_id"], []).append({
                "resource_type_id": r["resource_type_id"],
                "notes": r.get("notes") or "",
            })
    except Exception:
        pass

    col = master_db[MasterCollections.HAZARD_TYPES]
    inserted = updated = skipped = 0
    for r in rows:
        ht_id = str(r["id"])
        doc = {
            "_id": _new_id(),
            "hazard_type_id": ht_id,
            "name": r["name"],
            "display_name": r["display_name"],
            "category": r["category"],
            "source": r["source"],
            "owner_agency": r["owner_agency"],
            "description": r["description"],
            "default_risk_level": r["default_risk_level"],
            "default_likelihood": r["default_likelihood"],
            "default_severity": r["default_severity"],
            "default_control_measure": r["default_control_measure"],
            "default_ppe": r["default_ppe"],
            "default_safety_message": r["default_safety_message"],
            "is_active": bool(r["is_active"]),
            "notes": r["notes"],
            "created_at": r.get("created_at") or "",
            "updated_at": r.get("updated_at") or "",
            "created_by": r.get("created_by") or "",
            "updated_by": r.get("updated_by") or "",
            "aliases": aliases_by_id.get(r["id"], []),
            "mitigations": mitigations_by_id.get(r["id"], []),
            "ppe_items": ppe_by_id.get(r["id"], []),
            "references": references_by_id.get(r["id"], []),
            "resource_defaults": resource_defaults_by_id.get(r["id"], []),
        }
        existing = col.find_one({"hazard_type_id": ht_id})
        if existing is None:
            col.insert_one(doc)
            inserted += 1
        elif not existing.get("mitigations") and not existing.get("aliases"):
            col.replace_one({"hazard_type_id": ht_id}, {**doc, "_id": existing["_id"]})
            updated += 1
        else:
            skipped += 1
    _report(f"hazard_types ({updated} updated)", inserted, skipped)


def seed_hospitals(cur: sqlite3.Cursor, master_db) -> None:
    cur.execute("SELECT * FROM hospitals")
    rows = [dict(r) for r in cur.fetchall()]
    docs = [{
        "_id": _new_id(),
        "hospital_id": str(r["id"]),
        "name": r["name"],
        "hospital_type": r["type"],
        "phone": r["phone"],
        "fax": r["fax"],
        "email": r["email"],
        "contact": r["contact"],
        "address": r["address"],
        "city": r["city"],
        "state": r["state"],
        "zip": r["zip"],
        "notes": r["notes"],
        "is_active": bool(r["is_active"]) if r["is_active"] is not None else True,
    } for r in rows]
    col = master_db[MasterCollections.HOSPITALS]
    i, s = _seed_collection(col, docs, id_field="hospital_id")
    _report("hospitals", i, s)


def seed_resource_capabilities(cur: sqlite3.Cursor, master_db) -> None:
    try:
        cur.execute("SELECT * FROM resource_capabilities")
        rows = [dict(r) for r in cur.fetchall()]
    except Exception:
        return
    if not rows:
        return

    cap_aliases: dict[int, list[str]] = {}
    try:
        cur.execute("SELECT * FROM resource_capability_aliases")
        for r in (dict(x) for x in cur.fetchall()):
            cap_aliases.setdefault(r["capability_id"], []).append(r["alias"])
    except Exception:
        pass

    docs = [{
        "_id": _new_id(),
        "capability_id": str(r["id"]),
        "name": r["name"],
        "category": r.get("category") or "",
        "description": r.get("description") or "",
        "aliases": cap_aliases.get(r["id"], []),
        "is_active": bool(r.get("is_active", 1)),
        "notes": r.get("notes") or "",
    } for r in rows]
    col = master_db[MasterCollections.RESOURCE_CAPABILITIES]
    i, s = _seed_collection(col, docs, id_field="capability_id")
    _report("resource_capabilities", i, s)


def seed_resource_types(cur: sqlite3.Cursor, master_db) -> None:
    cur.execute("SELECT * FROM resource_types")
    rows = [dict(r) for r in cur.fetchall()]

    rt_aliases: dict[int, list[str]] = {}
    try:
        cur.execute("SELECT * FROM resource_type_aliases")
        for r in (dict(x) for x in cur.fetchall()):
            rt_aliases.setdefault(r["resource_type_id"], []).append(r["alias"])
    except Exception:
        pass

    cap_names_by_rt: dict[int, list[str]] = {}
    cap_ids_by_rt: dict[int, list[int]] = {}
    try:
        cur.execute("""
            SELECT rtc.resource_type_id, c.id, c.name
            FROM resource_type_capabilities rtc
            JOIN resource_capabilities c ON c.id = rtc.capability_id
        """)
        for r in (dict(x) for x in cur.fetchall()):
            cap_names_by_rt.setdefault(r["resource_type_id"], []).append(r["name"])
            cap_ids_by_rt.setdefault(r["resource_type_id"], []).append(r["id"])
    except Exception:
        pass

    components_by_rt: dict[int, list[dict]] = {}
    try:
        cur.execute("SELECT * FROM resource_type_components")
        for r in (dict(x) for x in cur.fetchall()):
            components_by_rt.setdefault(r["parent_resource_type_id"], []).append({
                "component_resource_type_id": r["component_resource_type_id"],
                "quantity": float(r.get("quantity") or 1.0),
                "unit": r.get("unit") or "each",
                "notes": r.get("notes") or "",
                "required": bool(r.get("required", 1)),
            })
    except Exception:
        pass

    fema_by_rt: dict[int, list[dict]] = {}
    try:
        cur.execute("SELECT * FROM resource_type_fema_mappings")
        for r in (dict(x) for x in cur.fetchall()):
            fema_by_rt.setdefault(r["resource_type_id"], []).append({
                "nims_name": r.get("nims_name") or "",
                "discipline": r.get("discipline") or "",
                "type_code": r.get("type_code") or "",
                "kind": r.get("kind") or "",
                "reference_url": r.get("reference_url") or "",
                "notes": r.get("notes") or "",
                "typed_level": r.get("typed_level") or "",
            })
    except Exception:
        pass

    col = master_db[MasterCollections.RESOURCE_TYPES]
    inserted = updated = skipped = 0
    for r in rows:
        rt_id = str(r["id"])
        doc = {
            "_id": _new_id(),
            "resource_type_id": rt_id,
            "name": r["name"],
            "planning_display_name": r["planning_display_name"],
            "category": r["category"],
            "source": r["source"],
            "owner_agency": r["owner_agency"],
            "description": r["description"],
            "default_unit": r["default_unit"],
            "typical_quantity": r["typical_quantity"],
            "typical_team_size": r["typical_team_size"],
            "is_kit_cache": bool(r["is_kit_cache"]),
            "is_consumable": bool(r["is_consumable"]),
            "is_active": bool(r["is_active"]),
            "notes": r["notes"],
            "created_at": r.get("created_at") or "",
            "updated_at": r.get("updated_at") or "",
            "created_by": r.get("created_by") or "",
            "updated_by": r.get("updated_by") or "",
            "aliases": rt_aliases.get(r["id"], []),
            "capability_ids": cap_ids_by_rt.get(r["id"], []),
            "capability_names": cap_names_by_rt.get(r["id"], []),
            "components": components_by_rt.get(r["id"], []),
            "fema_mappings": fema_by_rt.get(r["id"], []),
        }
        existing = col.find_one({"resource_type_id": rt_id})
        if existing is None:
            col.insert_one(doc)
            inserted += 1
        elif not existing.get("aliases") and not existing.get("fema_mappings"):
            col.replace_one({"resource_type_id": rt_id}, {**doc, "_id": existing["_id"]})
            updated += 1
        else:
            skipped += 1
    _report(f"resource_types ({updated} updated)", inserted, skipped)


def seed_agency_directory(cur: sqlite3.Cursor, master_db) -> None:
    cur.execute("SELECT * FROM agency_contacts")
    rows = [dict(r) for r in cur.fetchall()]
    docs = [{
        "_id": _new_id(),
        "agency_id": str(r["id"]),
        "name": r["name"],
        "agency": r["agency"],
        "contact_info": r["contact_info"],
        "notes": r["notes"],
    } for r in rows]
    col = master_db[MasterCollections.AGENCY_DIRECTORY]
    i, s = _seed_collection(col, docs, id_field="agency_id")
    _report("agency_directory", i, s)


def seed_team_types(cur: sqlite3.Cursor, master_db) -> None:
    """Seeds team_types from master.db into sarapp_master."""
    try:
        cur.execute("SELECT * FROM team_types")
        rows = [dict(r) for r in cur.fetchall()]
    except Exception:
        return
    if not rows:
        return
    docs = [{
        "_id": _new_id(),
        "int_id": int(r["id"]),
        "name": r.get("name", ""),
        "category": r.get("category") or "",
        "description": r.get("description") or "",
        "is_active": bool(r.get("is_active", 1)),
        "type_short": r.get("type_short"),
        "organization": r.get("organization"),
        "is_drone": bool(r.get("is_drone", 0)),
        "is_aviation": bool(r.get("is_aviation", 0)),
        "created_at": r.get("created_at", ""),
        "updated_at": r.get("updated_at", ""),
    } for r in rows]
    col = master_db[MasterCollections.TEAM_TYPES]
    i, s = _seed_collection(col, docs, id_field="int_id")
    _report("team_types", i, s)


def seed_task_types(master_db) -> None:
    """
    Reads task_categories and task_types from all incident DBs, deduplicates by
    category+name, and seeds a canonical list into master.
    """
    incidents_dir = _repo_root / "data" / "incidents"
    seen: set[tuple] = set()
    docs = []

    for db_path in sorted(incidents_dir.glob("*/incident.db")):
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT tc.name AS category, tt.name AS type_name
                FROM task_types tt
                JOIN task_categories tc ON tc.id = tt.categoryid
            """)
            for row in cur.fetchall():
                key = (row["category"], row["type_name"])
                if key not in seen and row["type_name"] and not row["type_name"].startswith("seed"):
                    seen.add(key)
                    docs.append({
                        "_id": _new_id(),
                        "task_type_id": f"{row['category'].lower()}-{row['type_name'].lower().replace(' ', '-')}",
                        "category": row["category"],
                        "name": row["type_name"],
                    })
        except Exception:
            pass
        finally:
            conn.close()

    if not docs:
        return
    col = master_db[MasterCollections.TASK_TYPES]
    i, s = _seed_collection(col, docs, id_field="task_type_id")
    _report("task_types", i, s)


def seed_meeting_templates(master_db) -> None:
    """
    Reads meeting_templates from any incident DB that has them (identical across all)
    and seeds into master.
    """
    incidents_dir = _repo_root / "data" / "incidents"
    docs = []

    for db_path in sorted(incidents_dir.glob("*/incident.db")):
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM meeting_templates")
            if cur.fetchone()[0] == 0:
                conn.close()
                continue
            cur.execute("SELECT * FROM meeting_templates WHERE active=1")
            for r in (dict(row) for row in cur.fetchall()):
                docs.append({
                    "_id": _new_id(),
                    "template_id": r["slug"],
                    "name": r["name"],
                    "default_duration_minutes": r.get("default_duration_minutes"),
                    "agenda_sections": json.loads(r["agenda_sections_json"]) if r.get("agenda_sections_json") else [],
                    "required_attendee_roles": json.loads(r["required_attendee_roles_json"]) if r.get("required_attendee_roles_json") else [],
                    "optional_attendee_roles": json.loads(r["optional_attendee_roles_json"]) if r.get("optional_attendee_roles_json") else [],
                    "prep_checklist": json.loads(r["prep_checklist_json"]) if r.get("prep_checklist_json") else [],
                    "agenda_checklist": json.loads(r["agenda_checklist_json"]) if r.get("agenda_checklist_json") else [],
                    "closeout_checklist": json.loads(r["closeout_checklist_json"]) if r.get("closeout_checklist_json") else [],
                    "appears_on_ics230_default": bool(r.get("appears_on_ics230_default", 0)),
                    "active": bool(r.get("active", 1)),
                })
            conn.close()
            break  # same templates in every incident DB — only need one
        except Exception:
            conn.close()
            continue

    if not docs:
        return
    col = master_db[MasterCollections.MEETING_TEMPLATES]
    i, s = _seed_collection(col, docs, id_field="template_id")
    _report("meeting_templates", i, s)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# Legacy flat-schema categories (forms_creator's old sqlite "category" column,
# e.g. "ICS") don't line up with the family-is-agency taxonomy the Mongo forms
# API uses. Best-effort mapping; anything unrecognized falls back to CUSTOM
# and should be re-categorized by hand later via the Forms Creator UI.
_LEGACY_CATEGORY_TO_AGENCY = {
    "ICS": "FEMA",
    "CAP": "CAP",
    "SAR": "SAR",
    "FEMA": "FEMA",
    "USCG": "USCG",
}


def _seed_legacy_flat_form_templates(cur: sqlite3.Cursor, master_db, table_name: str) -> None:
    """Migrate forms_creator's old flat template table (one row per template,
    fields embedded as fields_json, no family/version split) into the
    family -> template -> version collections the Mongo forms API expects.
    """
    cur.execute(f"SELECT * FROM {table_name}")
    rows = [dict(r) for r in cur.fetchall()]
    if not rows:
        return

    fam_col = master_db[MasterCollections.FORM_FAMILIES]
    tmpl_col = master_db[MasterCollections.FORM_TEMPLATES]
    ver_col = master_db[MasterCollections.FORM_TEMPLATE_VERSIONS]

    inserted = skipped = 0
    for r in rows:
        agency = _LEGACY_CATEGORY_TO_AGENCY.get((r.get("category") or "").strip().upper(), "CUSTOM")

        family = fam_col.find_one({"code": agency})
        if family is None:
            top = fam_col.find_one({}, sort=[("int_id", -1)])
            family = {
                "_id": _new_id(),
                "int_id": (top["int_id"] + 1) if top else 1,
                "code": agency,
                "title": agency,
                "description": None,
                "category": None,
                "default_agency": None,
                "is_active": True,
            }
            fam_col.insert_one(family)

        code = (r.get("subcategory") or r.get("name") or "").strip().upper().replace(" ", "_")
        existing_tmpl = tmpl_col.find_one({"family_int_id": family["int_id"], "code": code, "title": r["name"]})
        if existing_tmpl is not None:
            skipped += 1
            continue

        top_tmpl = tmpl_col.find_one({}, sort=[("int_id", -1)])
        tmpl_int_id = (top_tmpl["int_id"] + 1) if top_tmpl else 1
        top_ver = ver_col.find_one({}, sort=[("int_id", -1)])
        ver_int_id = (top_ver["int_id"] + 1) if top_ver else 1

        ver_col.insert_one({
            "_id": _new_id(),
            "int_id": ver_int_id,
            "template_int_id": tmpl_int_id,
            "version_number": r.get("version", 1),
            "version_label": None,
            "effective_date": None,
            "retired_date": None,
            "layout": {
                "background_path": r.get("background_path", ""),
                "page_count": r.get("page_count", 1),
                "schema_version": r.get("schema_version", 1),
            },
            "fields": json.loads(r["fields_json"]) if r.get("fields_json") else [],
            "bindings": [],
            "validation": [],
            "export_profiles": {},
            "source_asset_path": None,
            "checksum": None,
            "change_summary": "migrated from legacy sqlite form_templates",
            "created_by": None,
            "created_at": r.get("created_at", ""),
            "is_current": True,
        })
        tmpl_col.insert_one({
            "_id": _new_id(),
            "int_id": tmpl_int_id,
            "family_int_id": family["int_id"],
            "agency": agency,
            "system": None,
            "code": code,
            "title": r.get("name", ""),
            "description": None,
            "status": "active" if r.get("is_active", 1) else "retired",
            "current_version_int_id": ver_int_id,
            "compatibility": {},
            "tags": [],
            "created_by": None,
            "created_at": r.get("created_at", ""),
            "updated_at": r.get("updated_at", ""),
        })
        inserted += 1

    _report(f"{table_name} (legacy flat -> family/template/version)", inserted, skipped)


def seed_form_templates(cur: sqlite3.Cursor, master_db) -> None:
    def _table_exists(name: str) -> bool:
        cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
        return bool(cur.fetchone())

    for legacy_table in ("form_templates_hybrid",):
        if _table_exists(legacy_table):
            _seed_legacy_flat_form_templates(cur, master_db, legacy_table)

    if not _table_exists("form_families"):
        return

    cur.execute("SELECT * FROM form_families")
    families = [dict(r) for r in cur.fetchall()]
    family_docs = [{
        "_id": _new_id(),
        "int_id": r["id"],
        "code": r["code"],
        "title": r["title"],
        "description": r.get("description"),
        "category": r.get("category"),
        "default_agency": r.get("default_agency"),
        "is_active": bool(r.get("is_active", 1)),
        "created_at": r.get("created_at", ""),
        "updated_at": r.get("updated_at", ""),
    } for r in families]
    i, s = _seed_collection(master_db[MasterCollections.FORM_FAMILIES], family_docs, "int_id")
    _report("form_families", i, s)

    if not _table_exists("form_templates"):
        return
    cur.execute("SELECT * FROM form_templates")
    templates = [dict(r) for r in cur.fetchall()]
    template_docs = [{
        "_id": _new_id(),
        "int_id": r["id"],
        "family_int_id": r["family_id"],
        "agency": r.get("agency", ""),
        "system": r.get("system"),
        "code": r.get("code", ""),
        "title": r.get("title", ""),
        "description": r.get("description"),
        "status": r.get("status", "active"),
        "current_version_int_id": r.get("current_version_id"),
        "compatibility": json.loads(r["compatibility_json"]) if r.get("compatibility_json") else {},
        "tags": json.loads(r["tags_json"]) if r.get("tags_json") else [],
        "created_by": r.get("created_by"),
        "created_at": r.get("created_at", ""),
        "updated_at": r.get("updated_at", ""),
    } for r in templates]
    i, s = _seed_collection(master_db[MasterCollections.FORM_TEMPLATES], template_docs, "int_id")
    _report("form_templates", i, s)

    if not _table_exists("form_template_versions"):
        return
    cur.execute("SELECT * FROM form_template_versions")
    versions = [dict(r) for r in cur.fetchall()]
    version_docs = [{
        "_id": _new_id(),
        "int_id": r["id"],
        "template_int_id": r["template_id"],
        "version_number": r["version_number"],
        "version_label": r.get("version_label"),
        "effective_date": r.get("effective_date"),
        "retired_date": r.get("retired_date"),
        "layout": json.loads(r["layout_json"]) if r.get("layout_json") else {},
        "fields": json.loads(r["fields_json"]) if r.get("fields_json") else [],
        "bindings": json.loads(r["bindings_json"]) if r.get("bindings_json") else [],
        "validation": json.loads(r["validation_json"]) if r.get("validation_json") else [],
        "export_profiles": json.loads(r["export_profiles_json"]) if r.get("export_profiles_json") else {},
        "source_asset_path": r.get("source_asset_path"),
        "checksum": r.get("checksum"),
        "change_summary": r.get("change_summary"),
        "created_by": r.get("created_by"),
        "created_at": r.get("created_at", ""),
        "is_current": bool(r.get("is_current", 0)),
    } for r in versions]
    i, s = _seed_collection(master_db[MasterCollections.FORM_TEMPLATE_VERSIONS], version_docs, "int_id")
    _report("form_template_versions", i, s)


def main() -> int:
    print("=" * 60)
    print("SARApp master.db -> MongoDB seed")
    print("=" * 60)
    print(f"\nSQLite source : {_SQLITE_PATH}")

    mgr = DatabaseManager()
    if not mgr.is_connected():
        print("ERROR: Cannot connect to MongoDB. Check SARAPP_MONGO_URI.")
        return 1

    master_db = mgr.get_master_db()
    print(f"MongoDB target: {master_db.name}\n")

    reconcile_aircraft_collection(master_db)

    conn = _connect_sqlite()
    cur = conn.cursor()

    print(f"{'Collection':<30} {'Inserted':>8}   {'Skipped':>7}")
    print("-" * 55)

    seed_personnel(cur, master_db)
    seed_certification_types(cur, master_db)
    seed_vehicles(cur, master_db)
    seed_aircraft(cur, master_db)
    seed_equipment(cur, master_db)
    seed_radio_channels(cur, master_db)
    seed_hazard_types(cur, master_db)
    seed_hospitals(cur, master_db)
    seed_resource_capabilities(cur, master_db)
    seed_resource_types(cur, master_db)
    seed_agency_directory(cur, master_db)
    seed_team_types(cur, master_db)
    seed_form_templates(cur, master_db)

    conn.close()

    # These read from incident DBs directly, not master.db
    seed_task_types(master_db)
    seed_meeting_templates(master_db)

    print()
    print("Done. master.db was not modified.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
