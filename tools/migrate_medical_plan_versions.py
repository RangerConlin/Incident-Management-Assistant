"""One-time migration: ICS-206 medical plan versioning.

Rewrites existing per-incident data into the canonical versioned shape:

* ``medical_plan`` docs get ``version`` (1), ``approval_status`` (shared with
  ``modules.approvals``) and ``change_note``, a version-qualified ``plan_id``,
  and the expanded ``signatures`` fields.  A plan whose old free-text
  ``approved_by`` was filled in becomes ``approved``; the interim ``status``
  field (``draft``/``approved``) is converted and removed.
* ``ics_206_aid_stations`` docs get ``version`` = 1.
* The old one-plan-per-OP unique indexes are dropped and replaced.

Idempotent. Run with ``--dry-run`` first.  Reads ``SARAPP_MONGO_URI`` from the
environment.

    python tools/migrate_medical_plan_versions.py --dry-run
    python tools/migrate_medical_plan_versions.py
"""

from __future__ import annotations

import argparse
import os

from pymongo import ASCENDING, MongoClient

INCIDENT_DB_PREFIX = "sarapp_incident_"
SIGNATURE_DEFAULTS = {
    "prepared_by": "",
    "prepared_by_id": "",
    "position": "",
    "prepared_at": "",
    "date": "",
    "approved_by": "",
    "approved_by_id": "",
    "approved_by_position": "",
    "approved_at": "",
}


def migrate_incident(db, dry_run: bool) -> tuple[int, int]:
    incident_id = db.name[len(INCIDENT_DB_PREFIX):]
    plans = db["medical_plan"]
    aid = db["ics_206_aid_stations"]

    plan_count = 0
    plan_filter = {"$or": [{"version": {"$exists": False}}, {"status": {"$exists": True}}, {"approval_status": {"$exists": False}}]}
    for doc in plans.find(plan_filter):
        op = int(doc.get("op_period") or 0)
        signatures = dict(doc.get("signatures") or {})
        for key, default in SIGNATURE_DEFAULTS.items():
            signatures.setdefault(key, default)
        approved = doc.get("status") == "approved" or (
            "status" not in doc and bool(str(signatures.get("approved_by") or "").strip())
        )
        version = int(doc.get("version") or 1)
        updates = {
            "version": version,
            "approval_status": "approved" if approved else "not_started",
            "change_note": doc.get("change_note") or "",
            "plan_id": f"{incident_id}-MEDICAL-PLAN-{op}-V{version}",
            "signatures": signatures,
        }
        if not dry_run:
            plans.update_one({"_id": doc["_id"]}, {"$set": updates, "$unset": {"status": ""}})
        plan_count += 1

    aid_filter = {"version": {"$exists": False}}
    aid_count = aid.count_documents(aid_filter)
    if aid_count and not dry_run:
        aid.update_many(aid_filter, {"$set": {"version": 1}})

    if not dry_run and (plan_count or aid_count):
        existing = set(plans.index_information())
        for old in ("medical_plan_unique_per_op", "incident_id_1_op_period_1"):
            if old in existing:
                plans.drop_index(old)
        plans.create_index(
            [("incident_id", ASCENDING), ("op_period", ASCENDING), ("version", ASCENDING)],
            unique=True,
            name="medical_plan_unique_per_op_version",
        )
    return plan_count, aid_count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="report changes without writing")
    args = parser.parse_args()

    uri = os.environ.get("SARAPP_MONGO_URI")
    if not uri:
        raise SystemExit("SARAPP_MONGO_URI is not set")
    client = MongoClient(uri)
    for name in sorted(client.list_database_names()):
        if not name.startswith(INCIDENT_DB_PREFIX):
            continue
        plans, aid = migrate_incident(client[name], args.dry_run)
        verb = "would update" if args.dry_run else "updated"
        print(f"{name}: {verb} {plans} medical plan(s), {aid} aid station(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
