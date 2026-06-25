"""One-time rebuild of demo personnel data onto the new master-id scheme.

For each demo incident, this:
  1. Creates a master ``sarapp_master.personnel`` record for every row in
     that incident's ``incident_personnel`` collection (assigning a new
     global ``int_id`` and a generated ``badge_number``).
  2. Replaces the incident's ``incident_personnel`` docs with copies keyed
     by the new ``master_id`` (the old ``sqlite_id``-keyed docs are dropped).
  3. Remaps every personnel-id reference inside that same incident's Mongo
     collections (teams, tasks, communications_log) from the old leftover
     numeric id to the new master id.

This is a one-time data fix for demo/test data only — see the personnel
architecture discussion in conversation history. Safe to re-run; it skips
any incident already rebuilt.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sarapp_db.mongo.mongo_client import get_client

DEMO_INCIDENTS = ["2025-FAIR", "25-1-7985", "25-T-5874", "26-T-4301"]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _next_int_id(col) -> int:
    max_doc = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    return (max_doc["int_id"] + 1) if max_doc else 1


def rebuild_incident(client, incident_id: str) -> None:
    incident_db = client[f"sarapp_incident_{incident_id}"]
    personnel_col = incident_db["incident_personnel"]
    master_col = client["sarapp_master"]["personnel"]

    old_docs = list(personnel_col.find({"sqlite_id": {"$exists": True}}))
    if not old_docs:
        print(f"[{incident_id}] nothing to rebuild")
        return

    id_map: dict[str, int] = {}
    badge_map: dict[int, str] = {}
    next_id = _next_int_id(master_col)
    now = _utcnow()
    badge_seq = next_id * 1000  # arbitrary but unique-looking demo badge numbers

    for doc in old_docs:
        master_id = next_id
        next_id += 1
        badge_seq += 1
        badge_number = str(badge_seq)
        master_doc = {
            "int_id": master_id,
            "person_id": str(master_id),
            "personnel_id": str(master_id),
            "name": doc.get("name") or "",
            "rank": doc.get("rank"),
            "callsign": doc.get("callsign"),
            "primary_role": doc.get("role"),
            "phone": doc.get("phone"),
            "email": doc.get("email"),
            "home_unit": doc.get("organization") or doc.get("unit"),
            "badge_number": badge_number,
            "is_medic": bool(doc.get("is_medic", False)),
            "incident_history": [{"incident_id": incident_id, "date": now[:10]}],
            "created_at": now,
            "updated_at": now,
        }
        master_col.insert_one(master_doc)
        id_map[str(doc.get("sqlite_id"))] = master_id
        badge_map[master_id] = badge_number

    print(f"[{incident_id}] created {len(id_map)} master records ({min(id_map.values())}-{max(id_map.values())})")

    # Replace incident_personnel docs: drop old, insert new keyed by master_id
    new_copies = []
    for doc in old_docs:
        master_id = id_map[str(doc.get("sqlite_id"))]
        new_copies.append({
            "master_id": master_id,
            "incident_id": incident_id,
            "name": doc.get("name"),
            "rank": doc.get("rank"),
            "callsign": doc.get("callsign"),
            "role": doc.get("role"),
            "phone": doc.get("phone"),
            "email": doc.get("email"),
            "organization": doc.get("organization") or doc.get("unit"),
            "unit": doc.get("organization") or doc.get("unit"),
            "badge_number": badge_map[master_id],
            "is_medic": bool(doc.get("is_medic", False)),
            "team_id": doc.get("team_id"),
            "deleted": doc.get("deleted", False),
        })
    personnel_col.delete_many({"sqlite_id": {"$exists": True}})
    personnel_col.insert_many(new_copies)

    def remap_one(old_val):
        if old_val is None:
            return old_val
        return id_map.get(str(old_val), old_val)

    def remap_list(values):
        if not values:
            return values
        return [id_map.get(str(v), v) for v in values]

    # Teams: team_leader (int), leader_personnel_id (str), member_personnel_ids (list[str]),
    # personnel (list[int]), members_json (JSON string list[int])
    teams_col = incident_db["teams"]
    for team in teams_col.find():
        updates = {}
        if "team_leader" in team:
            updates["team_leader"] = remap_one(team.get("team_leader"))
        if "leader_personnel_id" in team:
            new_val = id_map.get(str(team.get("leader_personnel_id")))
            if new_val is not None:
                updates["leader_personnel_id"] = str(new_val)
        if "member_personnel_ids" in team:
            updates["member_personnel_ids"] = [
                str(id_map.get(str(v), v)) for v in (team.get("member_personnel_ids") or [])
            ]
        if "personnel" in team and isinstance(team.get("personnel"), list):
            updates["personnel"] = remap_list(team.get("personnel"))
        if "members_json" in team:
            import json
            try:
                members = json.loads(team.get("members_json") or "[]")
                updates["members_json"] = json.dumps(remap_list(members))
            except Exception:
                pass
        if updates:
            teams_col.update_one({"_id": team["_id"]}, {"$set": updates})

    # Tasks: assigned_personnel[].personnel_id (str)
    tasks_col = incident_db["tasks"]
    for task in tasks_col.find({"assigned_personnel": {"$exists": True, "$ne": []}}):
        assigned = task.get("assigned_personnel") or []
        changed = False
        for entry in assigned:
            old_pid = entry.get("personnel_id")
            new_pid = id_map.get(str(old_pid))
            if new_pid is not None:
                entry["personnel_id"] = str(new_pid)
                changed = True
        if changed:
            tasks_col.update_one({"_id": task["_id"]}, {"$set": {"assigned_personnel": assigned}})

    # Communications log: personnel_id (int)
    comms_col = incident_db["communications_log"]
    for entry in comms_col.find({"personnel_id": {"$exists": True, "$ne": None}}):
        new_pid = id_map.get(str(entry.get("personnel_id")))
        if new_pid is not None:
            comms_col.update_one({"_id": entry["_id"]}, {"$set": {"personnel_id": new_pid}})

    print(f"[{incident_id}] remapped teams, tasks, communications_log")


def main() -> None:
    client = get_client()
    for incident_id in DEMO_INCIDENTS:
        rebuild_incident(client, incident_id)


if __name__ == "__main__":
    main()
