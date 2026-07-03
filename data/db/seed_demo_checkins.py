"""Populate demo incident check-ins and resource-status links from team rosters."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DB = ROOT / "data" / "db"
if str(DATA_DB) not in sys.path:
    sys.path.insert(0, str(DATA_DB))

from sarapp_db.mongo.collection_names import IncidentCollections, MasterCollections  # noqa: E402
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: seed_demo_checkins.py <incident_id>")
        return 2

    incident_id = sys.argv[1]
    incident_db = get_incident_db(incident_id)
    master_db = get_master_db()
    teams_col = incident_db[IncidentCollections.TEAMS]
    checkins_col = incident_db[IncidentCollections.CHECKINS]
    rs_col = incident_db[IncidentCollections.RESOURCE_STATUS]
    personnel_col = master_db[MasterCollections.PERSONNEL]

    team_rows = list(teams_col.find({}, sort=[("id", 1)]))
    if not team_rows:
        print("no teams found")
        return 1

    person_rows = {}
    for row in personnel_col.find({}):
        pid = row.get("int_id", row.get("person_record", row.get("id")))
        if pid is None:
            continue
        person_rows[int(pid)] = dict(row)

    team_by_person: dict[int, dict[str, object]] = {}
    team_name_by_person: dict[int, str] = {}
    role_by_person: dict[int, str] = {}
    for team in team_rows:
        team_raw_id = team.get("int_id", team.get("id", team.get("team_id")))
        if team_raw_id is None:
            continue
        team_id = int(team_raw_id)
        team_name = str(team.get("name") or team.get("team_name") or team_id)
        members = team.get("member_personnel_ids") or team.get("members_json") or []
        if isinstance(members, str):
            try:
                members = json.loads(members)
            except Exception:
                members = []
        for pid in members:
            pid = int(pid)
            team_by_person.setdefault(pid, {"team_id": str(team_id), "team_name": team_name})
            team_name_by_person.setdefault(pid, team_name)
            if pid == int(team.get("team_leader") or 0):
                role_by_person[pid] = "Leader"
            else:
                role_by_person.setdefault(pid, "Member")

    existing_checkins = {
        int(doc["person_record"]): dict(doc)
        for doc in checkins_col.find({})
        if str(doc.get("person_record") or "").isdigit()
    }
    existing_resources = {
        int(doc["record_id"]): dict(doc)
        for doc in rs_col.find({"entity_type": "personnel"})
        if str(doc.get("record_id") or "").isdigit()
    }

    now = utc_now()
    checkin_inserts = 0
    checkin_updates = 0
    resource_updates = 0

    for pid, team_info in sorted(team_by_person.items()):
        person = person_rows.get(pid)
        if person is None:
            continue
        team_id = str(team_info["team_id"])
        team_name = str(team_info["team_name"])
        role_on_team = role_by_person.get(pid) or (person.get("role") or "")
        phone = person.get("phone") or ""
        callsign = person.get("callsign") or ""
        arrival_time = (
            existing_checkins.get(pid, {}).get("arrival_time")
            or existing_resources.get(pid, {}).get("checked_in_time")
            or now
        )
        status = "Assigned"

        checkin_doc = {
            "person_record": pid,
            "status": status,
            "ci_status": status,
            "personnel_status": "Assigned",
            "arrival_time": arrival_time,
            "location": "ICP",
            "location_other": None,
            "shift_start": None,
            "shift_end": None,
            "notes": None,
            "incident_callsign": callsign,
            "incident_phone": phone,
            "team_id": team_id,
            "role_on_team": role_on_team,
            "operational_period": None,
            "updated_at": now,
        }
        if pid in existing_checkins:
            checkins_col.update_one({"person_record": pid}, {"$set": checkin_doc})
            checkin_updates += 1
        else:
            checkin_doc["created_at"] = now
            checkins_col.insert_one(checkin_doc)
            checkin_inserts += 1

        rs_doc = {
            "entity_type": "personnel",
            "record_id": pid,
            "resource_id": str(pid),
            "resource_name": str(person.get("name") or pid),
            "resource_type": "Personnel",
            "status": status,
            "checked_in_time": arrival_time,
            "assigned_to": team_name,
            "assignment_reference": team_id,
            "location": "ICP",
            "last_updated": now,
            "updated_at": now,
        }
        if pid in existing_resources:
            rs_col.update_one({"record_id": pid, "entity_type": "personnel"}, {"$set": rs_doc})
        else:
            rs_doc["id"] = f"personnel-{pid}"
            rs_doc["status_log"] = [{"status": status, "timestamp": now, "changed_by": "Demo Seed"}]
            rs_doc["created_at"] = now
            rs_col.insert_one(rs_doc)
        resource_updates += 1

    print(
        f"incident={incident_id} checkins updated={checkin_updates} inserted={checkin_inserts} "
        f"resource_status updated={resource_updates}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
