"""One-time migration: consolidate all entity ID fields to the *_record / *_id scheme.

Personnel:
  int_id          → person_record  (internal integer key)
  badge_number    → person_id      (user-visible string)
  Removed: personnel_id, person_id (old), id, int_id, sqlite_id, badge_number

Equipment:
  int_id → equipment_record
  Removed: int_id

Aircraft:
  int_id       → aircraft_record
  aircraft_id  removed (was an old index field, not stored on docs)
  Removed: int_id

Vehicles:
  vehicle_id (int)    → vehicle_record; vehicle_id set to "" (user fills in later)
  vehicle_id (string) → kept as vehicle_id; vehicle_record auto-assigned
  Removed: old vehicle_id integer field

Incident personnel (per incident DB):
  master_id   → person_record
  badge_number → person_id
  Removed: master_id, person_id (old), sqlite_id, badge_number

Philosophy: if a record cannot be cleanly migrated it is deleted rather than
carried forward with corrupt or ambiguous state.

Safe to re-run — each step checks for already-migrated docs.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from sarapp_db.mongo.mongo_client import get_client


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _next_record_id(col, field: str) -> int:
    max_doc = col.find_one({field: {"$exists": True}}, sort=[(field, -1)])
    return (int(max_doc[field]) if max_doc else 0) + 1


# ---------------------------------------------------------------------------
# Master: Personnel
# ---------------------------------------------------------------------------

def migrate_personnel(client) -> None:
    col = client["sarapp_master"]["personnel"]
    total = col.count_documents({})
    print(f"[personnel] {total} master records found")

    deleted = 0
    migrated = 0
    already_done = 0

    for doc in list(col.find({})):
        if "person_record" in doc:
            already_done += 1
            continue

        int_id = doc.get("int_id")
        if int_id is None:
            # No resolvable integer ID — delete
            col.delete_one({"_id": doc["_id"]})
            deleted += 1
            continue

        badge = doc.get("badge_number") or ""

        col.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "person_record": int(int_id),
                    "person_id": badge,
                },
                "$unset": {
                    "int_id": "",
                    "personnel_id": "",
                    "badge_number": "",
                    "id": "",
                    "sqlite_id": "",
                    # old person_id (string form of int_id) overwritten by $set above
                    # but we need to handle the case where $set and $unset touch the
                    # same key — MongoDB forbids that in one op, so we must handle
                    # person_id separately via $set above which overwrites the old value.
                },
            },
        )
        migrated += 1

    # Clean up leftover old person_id field that wasn't caught by the unset
    # (because $set person_id and $unset person_id can't coexist in one op,
    # the $set wins; old string values are overwritten by the badge value above)
    print(f"[personnel] migrated={migrated} skipped(done)={already_done} deleted={deleted}")


# ---------------------------------------------------------------------------
# Master: Equipment
# ---------------------------------------------------------------------------

def migrate_equipment(client) -> None:
    col = client["sarapp_master"]["equipment"]
    total = col.count_documents({})
    print(f"[equipment] {total} master records found")

    deleted = 0
    migrated = 0
    already_done = 0

    for doc in list(col.find({})):
        if "equipment_record" in doc:
            already_done += 1
            continue

        int_id = doc.get("int_id")
        if int_id is None:
            col.delete_one({"_id": doc["_id"]})
            deleted += 1
            continue

        col.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {"equipment_record": int(int_id)},
                "$unset": {"int_id": ""},
            },
        )
        migrated += 1

    print(f"[equipment] migrated={migrated} skipped(done)={already_done} deleted={deleted}")


# ---------------------------------------------------------------------------
# Master: Aircraft
# ---------------------------------------------------------------------------

def migrate_aircraft(client) -> None:
    col = client["sarapp_master"]["aircraft"]
    total = col.count_documents({})
    print(f"[aircraft] {total} master records found")

    deleted = 0
    migrated = 0
    already_done = 0

    for doc in list(col.find({})):
        if "aircraft_record" in doc:
            already_done += 1
            continue

        int_id = doc.get("int_id")
        if int_id is None:
            col.delete_one({"_id": doc["_id"]})
            deleted += 1
            continue

        # aircraft_id was an old index field — if present on the doc, remove it
        unset_fields: dict = {"int_id": ""}
        if "aircraft_id" in doc and doc["aircraft_id"] != doc.get("tail_number"):
            unset_fields["aircraft_id"] = ""

        col.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {"aircraft_record": int(int_id)},
                "$unset": unset_fields,
            },
        )
        migrated += 1

    print(f"[aircraft] migrated={migrated} skipped(done)={already_done} deleted={deleted}")


# ---------------------------------------------------------------------------
# Master: Vehicles
# ---------------------------------------------------------------------------

def migrate_vehicles(client) -> None:
    col = client["sarapp_master"]["vehicles"]
    total = col.count_documents({})
    print(f"[vehicles] {total} master records found")

    migrated = 0
    already_done = 0
    counter = _next_record_id(col, "vehicle_record")

    for doc in list(col.find({})):
        if "vehicle_record" in doc:
            already_done += 1
            continue

        old_vid = doc.get("vehicle_id")

        if isinstance(old_vid, int):
            # Was auto-assigned integer — promote to vehicle_record, clear vehicle_id
            col.update_one(
                {"_id": doc["_id"]},
                {
                    "$set": {"vehicle_record": old_vid, "vehicle_id": ""},
                },
            )
        elif old_vid is not None:
            # Was a user-supplied string — keep it, assign new vehicle_record
            col.update_one(
                {"_id": doc["_id"]},
                {"$set": {"vehicle_record": counter}},
            )
            counter += 1
        else:
            # No vehicle_id at all — assign vehicle_record, leave vehicle_id blank
            col.update_one(
                {"_id": doc["_id"]},
                {"$set": {"vehicle_record": counter, "vehicle_id": ""}},
            )
            counter += 1

        migrated += 1

    print(f"[vehicles] migrated={migrated} skipped(done)={already_done}")


# ---------------------------------------------------------------------------
# Incident personnel (all incident DBs)
# ---------------------------------------------------------------------------

def migrate_incident_checkins(client) -> None:
    """Migrate checkins collection: person_id (string key) → person_record (int)."""
    db_names = [n for n in client.list_database_names() if n.startswith("sarapp_incident_")]
    for db_name in db_names:
        incident_db = client[db_name]
        for coll_name in ("checkins", "checkin_history"):
            col = incident_db[coll_name]
            if col.count_documents({}) == 0:
                continue
            deleted = migrated = already_done = 0
            for doc in list(col.find({})):
                if "person_record" in doc:
                    already_done += 1
                    continue
                old_pid = doc.get("person_id")
                if old_pid is not None and str(old_pid).isdigit():
                    col.update_one(
                        {"_id": doc["_id"]},
                        {
                            "$set": {"person_record": int(old_pid)},
                            "$unset": {"person_id": ""},
                        },
                    )
                    migrated += 1
                else:
                    col.delete_one({"_id": doc["_id"]})
                    deleted += 1
            print(f"  [{db_name}/{coll_name}] migrated={migrated} skipped={already_done} deleted={deleted}")


def migrate_incident_personnel(client) -> None:
    db_names = [n for n in client.list_database_names() if n.startswith("sarapp_incident_")]
    print(f"[incident_personnel] found {len(db_names)} incident database(s)")

    for db_name in db_names:
        incident_db = client[db_name]
        col = incident_db["incident_personnel"]
        total = col.count_documents({})
        if total == 0:
            continue

        deleted = 0
        migrated = 0
        already_done = 0

        for doc in list(col.find({})):
            if "person_record" in doc:
                already_done += 1
                continue

            master_id = doc.get("master_id")
            if master_id is None:
                col.delete_one({"_id": doc["_id"]})
                deleted += 1
                continue

            badge = doc.get("badge_number") or ""

            col.update_one(
                {"_id": doc["_id"]},
                {
                    "$set": {
                        "person_record": int(master_id),
                        "person_id": badge,
                    },
                    "$unset": {
                        "master_id": "",
                        "badge_number": "",
                        "sqlite_id": "",
                        # old person_id overwritten by $set above
                    },
                },
            )
            migrated += 1

        print(f"  [{db_name}] migrated={migrated} skipped(done)={already_done} deleted={deleted}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run() -> None:
    client = get_client()
    print("=== migrate_record_ids: starting ===")
    migrate_personnel(client)
    migrate_equipment(client)
    migrate_aircraft(client)
    migrate_vehicles(client)
    migrate_incident_checkins(client)
    migrate_incident_personnel(client)
    print("=== migrate_record_ids: done ===")


if __name__ == "__main__":
    run()
