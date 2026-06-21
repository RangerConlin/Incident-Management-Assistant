"""Personnel check-in roster API router (per-incident)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from sarapp_db.mongo.mongo_client import get_client
from sarapp_db.mongo.database_manager import DB_MASTER, get_incident_db_name
from sarapp_db.mongo.collection_names import MasterCollections, IncidentCollections

router = APIRouter()


def _master():
    return get_client()[DB_MASTER]


def _incident(incident_id: str):
    return get_client()[get_incident_db_name(incident_id)]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
    col = _master()[MasterCollections.PERSONNEL]
    term = (q or "").strip().lower()
    docs = list(col.find().sort("name", 1))
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
    col = _master()[MasterCollections.PERSONNEL]
    doc = (
        col.find_one({"person_id": person_id})
        or col.find_one({"id": person_id})
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Person not found")
    return _normalize_person(doc)


# ---------------------------------------------------------------------------
# Roster filters reference data
# ---------------------------------------------------------------------------

@router.get("/roles")
def get_distinct_roles(incident_id: str) -> list[str]:
    col = _incident(incident_id)[IncidentCollections.CHECKINS]
    values = col.distinct("role_on_team", {"role_on_team": {"$nin": [None, ""]}})
    master_col = _master()[MasterCollections.PERSONNEL]
    for field in ("primary_role", "role"):
        vals = master_col.distinct(field, {field: {"$nin": [None, ""]}})
        values.extend(vals)
    return sorted({str(v).strip() for v in values if v})


@router.get("/teams")
def get_distinct_teams(incident_id: str) -> list[dict[str, Any]]:
    col = _incident(incident_id)[IncidentCollections.TEAMS]
    docs = list(col.find({}, {"team_id": 1, "name": 1}).sort("name", 1))
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
    col = _incident(incident_id)[IncidentCollections.CHECKINS]
    query: dict[str, Any] = {}
    if ci_status and ci_status != "All":
        query["ci_status"] = ci_status
    if personnel_status and personnel_status != "All":
        query["personnel_status"] = personnel_status
    if team and team not in ("All", "—", ""):
        query["team_id"] = team
    if not include_no_show:
        query["ci_status"] = {"$ne": "NoShow"} if "ci_status" not in query else query["ci_status"]

    docs = list(col.find(query).sort("updated_at", -1))
    master_col = _master()[MasterCollections.PERSONNEL]
    result = []

    for d in docs:
        person_id = d.get("person_id")
        identity = (
            master_col.find_one({"person_id": person_id})
            or master_col.find_one({"id": person_id})
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
            "ci_status": ci_st,
            "personnel_status": p_st,
            "updated_at": d.get("updated_at"),
            "row_class": "row-demob" if ci_st == "Demobilized" else None,
            "ui_flags": {
                "hidden_by_default": ci_st == "NoShow",
                "grayed": ci_st == "Demobilized",
            },
        })

    result.sort(key=lambda r: (r.get("name") or "").lower())
    return result


# ---------------------------------------------------------------------------
# Check-in record CRUD
# ---------------------------------------------------------------------------

@router.get("/{person_id}")
def fetch_checkin(incident_id: str, person_id: str) -> dict[str, Any]:
    col = _incident(incident_id)[IncidentCollections.CHECKINS]
    doc = col.find_one({"person_id": person_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Check-in record not found")
    return _normalize_checkin(doc)


@router.put("/{person_id}")
def save_checkin(
    incident_id: str, person_id: str, body: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    col = _incident(incident_id)[IncidentCollections.CHECKINS]
    body.pop("_id", None)
    body["person_id"] = person_id
    now = _utcnow()
    body.setdefault("created_at", now)
    body["updated_at"] = now

    if body.get("team_id") in ("—", ""):
        body["team_id"] = None

    existing = col.find_one({"person_id": person_id})
    if existing:
        body.setdefault("created_at", existing.get("created_at", now))
        col.update_one({"person_id": person_id}, {"$set": body})
    else:
        col.insert_one(body)

    # Mirror contact fields back to master personnel
    try:
        master_col = _master()[MasterCollections.PERSONNEL]
        ident = (
            master_col.find_one({"person_id": person_id})
            or master_col.find_one({"id": person_id})
        )
        if ident:
            updates: dict[str, Any] = {}
            if body.get("incident_phone"):
                updates["phone"] = body["incident_phone"]
            if body.get("incident_callsign"):
                updates["callsign"] = body["incident_callsign"]
            if body.get("role_on_team"):
                updates["primary_role"] = body["role_on_team"]
            if updates:
                master_col.update_one({"_id": ident["_id"]}, {"$set": updates})
    except Exception:
        pass

    doc = col.find_one({"person_id": person_id})
    return _normalize_checkin(doc or body)


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

@router.post("/history")
def log_history(
    incident_id: str, body: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    col = _incident(incident_id)[IncidentCollections.CHECKIN_HISTORY]
    body["ts"] = body.get("ts") or _utcnow()
    col.insert_one(body)
    body.pop("_id", None)
    return body


@router.get("/history/{person_id}")
def list_history(incident_id: str, person_id: str) -> list[dict[str, Any]]:
    col = _incident(incident_id)[IncidentCollections.CHECKIN_HISTORY]
    docs = list(col.find({"person_id": person_id}).sort("ts", -1))
    for d in docs:
        d.pop("_id", None)
    return docs
