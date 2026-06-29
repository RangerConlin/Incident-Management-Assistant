"""Personnel check-in roster API router (per-incident)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from sarapp_db.mongo.database_manager import get_incident_db, get_master_db
from sarapp_db.mongo.collection_names import MasterCollections, IncidentCollections
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()
DERIVED_CHECKED_IN_STATUSES = {
    "Available",
    "Assigned",
    "Out of Service",
    "Preparing for Demobilization",
    "Checked In",
}


class PersonnelRepository(BaseRepository):
    collection_name = MasterCollections.PERSONNEL
    soft_deletes = False


class CheckinsRepository(BaseRepository):
    collection_name = IncidentCollections.CHECKINS
    soft_deletes = False


class TeamsRepository(BaseRepository):
    collection_name = IncidentCollections.TEAMS
    soft_deletes = False


class CheckinHistoryRepository(BaseRepository):
    collection_name = IncidentCollections.CHECKIN_HISTORY
    soft_deletes = False


def _personnel_repo() -> PersonnelRepository:
    return PersonnelRepository(get_master_db())


def _checkins_repo(incident_id: str) -> CheckinsRepository:
    return CheckinsRepository(get_incident_db(incident_id))


def _teams_repo(incident_id: str) -> TeamsRepository:
    return TeamsRepository(get_incident_db(incident_id))


def _checkin_history_repo(incident_id: str) -> CheckinHistoryRepository:
    return CheckinHistoryRepository(get_incident_db(incident_id))


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _is_checked_in_status(status: Any) -> bool:
    return str(status or "").strip() in DERIVED_CHECKED_IN_STATUSES


def _normalize_person(doc: dict[str, Any]) -> dict[str, Any]:
    d = dict(doc)
    d.pop("_id", None)
    person_id = d.get("person_id") or d.get("id")
    d["id"] = str(person_id) if person_id is not None else None
    d["primary_role"] = d.get("primary_role") or d.get("role") or d.get("rank")
    d["phone"] = d.get("phone") or d.get("contact")
    d["home_unit"] = d.get("home_unit") or d.get("unit")
    return d


def _normalize_checkin(doc: dict[str, Any]) -> dict[str, Any]:
    d = dict(doc)
    d.pop("_id", None)
    d["status"] = d.get("status") or d.get("ci_status") or d.get("planning_status") or d.get("personnel_status") or "Pending"
    d["checked_in"] = _is_checked_in_status(d["status"])
    d["checkin_status"] = "Checked In" if d["checked_in"] else "Not Checked In"
    return d


# ---------------------------------------------------------------------------
# Master personnel lookup (used during check-in search)
# ---------------------------------------------------------------------------

@router.get("/personnel/search")
def search_personnel(
    incident_id: str,
    q: str = Query(""),
    limit: int = Query(50),
) -> list[dict[str, Any]]:
    repo = _personnel_repo()
    term = (q or "").strip().lower()
    docs = repo.find_many({}, sort=[("name", 1)])
    results = []
    for d in docs:
        if term:
            pid = str(d.get("person_id") or d.get("id") or "")
            haystack = "|".join(filter(None, [
                pid,
                d.get("name") or "",
                d.get("callsign") or "",
                d.get("phone") or "",
                d.get("contact") or "",
            ])).lower()
            if term not in haystack:
                continue
        results.append(_normalize_person(d))
        if len(results) >= limit:
            break
    return results


@router.get("/personnel/{person_id}")
def get_person_identity(incident_id: str, person_id: str) -> dict[str, Any]:
    repo = _personnel_repo()
    doc = (
        repo.find_one({"person_id": person_id})
        or repo.find_one({"id": person_id})
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Person not found")
    return _normalize_person(doc)


# ---------------------------------------------------------------------------
# Roster filters reference data
# ---------------------------------------------------------------------------

@router.get("/roles")
def get_distinct_roles(incident_id: str) -> list[str]:
    checkins_repo = _checkins_repo(incident_id)
    values = checkins_repo._col.distinct("role_on_team", {"role_on_team": {"$nin": [None, ""]}})
    personnel_repo = _personnel_repo()
    for field in ("primary_role", "role"):
        vals = personnel_repo._col.distinct(field, {field: {"$nin": [None, ""]}})
        values.extend(vals)
    return sorted({str(v).strip() for v in values if v})


@router.get("/teams")
def get_distinct_teams(incident_id: str) -> list[dict[str, Any]]:
    repo = _teams_repo(incident_id)
    docs = repo.find_many({}, sort=[("name", 1)])
    result = []
    for d in docs:
        tid = d.get("team_id") or d.get("int_id")
        name = d.get("name") or str(tid)
        if tid is None:
            continue
        result.append({"team_id": str(tid), "team_name": name})
    return result


# ---------------------------------------------------------------------------
# Check-in roster
# ---------------------------------------------------------------------------

@router.get("/roster")
def fetch_roster(
    incident_id: str,
    q: str = Query(""),
    ci_status: str = Query(""),
    personnel_status: str = Query(""),
    role: str = Query(""),
    team: str = Query(""),
    include_no_show: bool = Query(False),
) -> list[dict[str, Any]]:
    repo = _checkins_repo(incident_id)
    query: dict[str, Any] = {}
    if ci_status and ci_status != "All":
        query["ci_status"] = ci_status
    if personnel_status and personnel_status != "All":
        query["personnel_status"] = personnel_status
    if team and team not in ("All", "—", ""):
        query["team_id"] = team
    if not include_no_show:
        query["ci_status"] = {"$ne": "NoShow"} if "ci_status" not in query else query["ci_status"]

    docs = repo.find_many(query, sort=[("updated_at", -1)])
    personnel_repo = _personnel_repo()
    result = []

    for d in docs:
        person_id = d.get("person_id")
        identity = (
            personnel_repo.find_one({"person_id": person_id})
            or personnel_repo.find_one({"id": person_id})
        ) if person_id else None

        if identity is None and person_id:
            identity = {"id": person_id, "name": person_id}

        name = (identity or {}).get("name") or person_id or ""
        if q:
            t = q.strip().lower()
            callsign = d.get("incident_callsign") or (identity or {}).get("callsign") or ""
            phone = d.get("incident_phone") or (identity or {}).get("phone") or ""
            haystack = "|".join(filter(None, [
                person_id, name, callsign, phone
            ])).lower()
            if t not in haystack:
                continue

        row_role = d.get("role_on_team") or (identity or {}).get("primary_role") or (identity or {}).get("role")
        if role and role != "All" and row_role != role:
            continue

        ci_st = d.get("ci_status", "")
        p_st = d.get("personnel_status", "")
        team_label = d.get("team_name") or d.get("team_id") or "—"

        result.append({
            "person_id": person_id,
            "name": name,
            "role": row_role,
            "team": team_label,
            "team_id": d.get("team_id"),
            "phone": (identity or {}).get("phone") or d.get("incident_phone"),
            "callsign": d.get("incident_callsign") or (identity or {}).get("callsign"),
            "status": d.get("status") or d.get("ci_status") or d.get("planning_status") or "Pending",
            "checked_in": _is_checked_in_status(d.get("status") or d.get("ci_status") or d.get("planning_status")),
            "updated_at": d.get("updated_at"),
            "row_class": "row-demob" if str(d.get("status") or ci_st) == "Demobilized" else None,
            "ui_flags": {
                "hidden_by_default": str(d.get("status") or ci_st) == "NoShow",
                "grayed": str(d.get("status") or ci_st) == "Demobilized",
            },
        })

    result.sort(key=lambda r: (r.get("name") or "").lower())
    return result


# ---------------------------------------------------------------------------
# Check-in record CRUD
# ---------------------------------------------------------------------------

@router.get("/{person_id}")
def fetch_checkin(incident_id: str, person_id: str) -> dict[str, Any]:
    repo = _checkins_repo(incident_id)
    doc = repo.find_one({"person_id": person_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Check-in record not found")
    return _normalize_checkin(doc)


@router.put("/{person_id}")
def save_checkin(
    incident_id: str, person_id: str, body: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    repo = _checkins_repo(incident_id)
    body.pop("_id", None)
    body["person_id"] = person_id

    if body.get("team_id") in ("—", ""):
        body["team_id"] = None

    existing = repo.find_one({"person_id": person_id})
    if existing:
        repo.update_one(existing["_id"], body)
        doc = repo.find_by_id(existing["_id"])
    else:
        doc = repo.insert_one(body)

    # Mirror contact fields back to master personnel, log this incident on
    # the master record's check-in history, and ensure the incident has a
    # local copy of this person's identity keyed by the master id.
    try:
        personnel_repo = _personnel_repo()
        ident = (
            personnel_repo.find_one({"person_id": person_id})
            or personnel_repo.find_one({"id": person_id})
        )
        if ident:
            updates: dict[str, Any] = {}
            if body.get("incident_phone"):
                updates["phone"] = body["incident_phone"]
            if body.get("incident_callsign"):
                updates["callsign"] = body["incident_callsign"]
            if body.get("role_on_team"):
                updates["primary_role"] = body["role_on_team"]

            today = _utcnow()[:10]
            history = ident.get("incident_history") or []
            if not any(h.get("incident_id") == incident_id and h.get("date") == today for h in history):
                updates["incident_history"] = history + [{"incident_id": incident_id, "date": today}]

            if updates:
                personnel_repo.update_one(ident["_id"], updates)

            master_id = ident.get("int_id")
            if master_id is not None:
                from sarapp_db.mongo.client import get_db
                incident_personnel_col = get_db(f"sarapp_incident_{incident_id}")["incident_personnel"]
                copy_fields = {
                    "master_id": master_id,
                    "incident_id": incident_id,
                    "name": ident.get("name"),
                    "rank": ident.get("rank"),
                    "callsign": updates.get("callsign", ident.get("callsign")),
                    "role": updates.get("primary_role", ident.get("primary_role") or ident.get("role")),
                    "phone": updates.get("phone", ident.get("phone")),
                    "email": ident.get("email"),
                    "organization": ident.get("home_unit") or ident.get("organization"),
                    "unit": ident.get("home_unit") or ident.get("unit"),
                    "badge_number": ident.get("badge_number"),
                    "is_medic": bool(ident.get("is_medic", False)),
                }
                incident_personnel_col.update_one(
                    {"master_id": master_id}, {"$set": copy_fields}, upsert=True
                )
    except Exception:
        pass

    return _normalize_checkin(doc)


# ---------------------------------------------------------------------------
# Team check-in / disband (ICS-211 workflow)
# ---------------------------------------------------------------------------

@router.post("/teams/{team_id}/checkin")
def team_checkin(
    incident_id: str, team_id: str, body: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    """Check in a team and optionally its assets.

    Body fields:
    - keep_together (bool): if true, mark team checked_in; if false, disband
    - check_in_assets (list of str): asset record ids to check in (optional)
    - checked_in_by (str): user id
    - checkin_notes (str): optional notes
    - bulk_checkin_id (str): optional batch identifier
    """
    teams_repo = _teams_repo(incident_id)
    team_doc = teams_repo.find_one({"team_id": team_id}) or teams_repo.find_one({"int_id": team_id})
    if not team_doc:
        raise HTTPException(status_code=404, detail="Team not found")

    now = _utcnow()
    keep_together = body.get("keep_together", True)
    checked_in_by = body.get("checked_in_by")
    checkin_notes = body.get("checkin_notes")
    bulk_checkin_id = body.get("bulk_checkin_id")

    status = body.get("status") or (
        "Assigned"
        if any(team_doc.get(field) not in (None, "", [], {}) for field in ("current_task_id", "operational_unit_id", "assignment"))
        else "Available"
    )
    updates: dict[str, Any] = {
        "status": status,
        "checked_in_at": now,
        "checked_in_by": checked_in_by,
    }
    if checkin_notes:
        updates["checkin_notes"] = checkin_notes
    if bulk_checkin_id:
        updates["bulk_checkin_id"] = bulk_checkin_id

    if not keep_together:
        updates["disbanded"] = True
        updates["disbanded_at"] = now
        updates["disbanded_by"] = checked_in_by
    teams_repo.update_one(team_doc["_id"], updates)

    # Log the check-in event in history
    history_repo = _checkin_history_repo(incident_id)
    history_repo.insert_one({
        "event_type": "team.checkin",
        "team_id": team_id,
        "actor": checked_in_by,
        "ts": now,
        "payload": {
            "keep_together": keep_together,
            "bulk_checkin_id": bulk_checkin_id,
            "checkin_notes": checkin_notes,
        },
    })

    # Return the updated team document
    updated = teams_repo.find_by_id(team_doc["_id"])
    updated.pop("_id", None)
    return updated


@router.post("/teams/{team_id}/disband")
def team_disband(
    incident_id: str, team_id: str, body: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    """Disband a team (separate from check-in)."""
    teams_repo = _teams_repo(incident_id)
    team_doc = teams_repo.find_one({"team_id": team_id}) or teams_repo.find_one({"int_id": team_id})
    if not team_doc:
        raise HTTPException(status_code=404, detail="Team not found")

    now = _utcnow()
    disbanded_by = body.get("disbanded_by")

    updates = {
        "disbanded": True,
        "disbanded_at": now,
        "disbanded_by": disbanded_by,
    }
    teams_repo.update_one(team_doc["_id"], updates)

    # Log in history
    history_repo = _checkin_history_repo(incident_id)
    history_repo.insert_one({
        "event_type": "team.disband",
        "team_id": team_id,
        "actor": disbanded_by,
        "ts": now,
        "payload": {},
    })

    updated = teams_repo.find_by_id(team_doc["_id"])
    updated.pop("_id", None)
    return updated


@router.get("/teams/checked-state")
def list_teams_by_checkin_state(
    incident_id: str,
    checked_in: bool = Query(False),
    include_disbanded: bool = Query(False),
) -> list[dict[str, Any]]:
    """List teams filtered by check-in state.

    Default returns only non-disbanded, checked-in teams (for the
    normal Team Status Board). Set checked_in=false to get unchecked
    teams for planning views.
    """
    repo = _teams_repo(incident_id)
    query: dict[str, Any] = {}
    if checked_in:
        query["status"] = {"$in": sorted(DERIVED_CHECKED_IN_STATUSES)}
    else:
        query["status"] = {"$nin": sorted(DERIVED_CHECKED_IN_STATUSES)}
    if not include_disbanded:
        query["disbanded"] = {"$ne": True}
    docs = repo.find_many(query, sort=[("name", 1)])
    result = []
    for d in docs:
        d.pop("_id", None)
        # Ensure boolean fields are properly typed
        d["checked_in"] = _is_checked_in_status(d.get("status"))
        d["disbanded"] = bool(d.get("disbanded", False))
        result.append(d)
    return result


# ---------------------------------------------------------------------------
# Planning statuses
# ---------------------------------------------------------------------------

@router.get("/planning-statuses")
def list_planning_status_resources(
    incident_id: str,
    status: str = Query(""),
) -> list[dict[str, Any]]:
    """List check-in records with pre-arrival planning statuses."""
    repo = _checkins_repo(incident_id)
    planning_stati = ["Requested", "Ordered", "Enroute", "Expected", "Cancelled", "Not Coming", "Pending", "Staged"]
    clause: dict[str, Any] = {"$in": planning_stati}
    if status and status in planning_stati:
        clause = status
    query: dict[str, Any] = {"status": clause}
    docs = repo.find_many(query, sort=[("updated_at", -1)])
    result = []
    for d in docs:
        d.pop("_id", None)
        result.append(d)
    return result


@router.patch("/{person_id}/status")
def patch_checkin_status(
    incident_id: str, person_id: str, body: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    """Update the canonical linear status on an existing check-in record."""
    repo = _checkins_repo(incident_id)
    existing = repo.find_one({"person_id": person_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Check-in record not found")

    patch: dict[str, Any] = {}
    if "status" in body:
        patch["status"] = body["status"]
    elif "ci_status" in body:
        patch["status"] = body["ci_status"]
    elif "planning_status" in body:
        patch["status"] = body["planning_status"]

    if not patch:
        raise HTTPException(status_code=400, detail="No updatable fields provided")

    patch["updated_at"] = _utcnow()
    repo.update_one(existing["_id"], patch)
    doc = repo.find_by_id(existing["_id"])
    doc.pop("_id", None)
    return doc


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

@router.post("/history")
def log_history(
    incident_id: str, body: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    repo = _checkin_history_repo(incident_id)
    body["ts"] = body.get("ts") or _utcnow()
    doc = repo.insert_one(body)
    doc.pop("_id", None)
    return doc


@router.get("/history/{person_id}")
def list_history(incident_id: str, person_id: str) -> list[dict[str, Any]]:
    repo = _checkin_history_repo(incident_id)
    docs = repo.find_many({"person_id": person_id}, sort=[("ts", -1)])
    for d in docs:
        d.pop("_id", None)
    return docs
