"""Personnel check-in roster API router (per-incident)."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from sarapp_db.mongo.database_manager import get_incident_db, get_master_db
from sarapp_db.mongo.collection_names import MasterCollections, IncidentCollections
from sarapp_db.mongo.int_id import _ensure_int_ids
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()
logger = logging.getLogger(__name__)
DERIVED_CHECKED_IN_STATUSES = {
    "Available",
    "Assigned",
    "Out of Service",
    "Preparing for Demobilization",
    "Checked In",
}

_PERSON_RECORD = "person_record"


class PersonnelRepository(BaseRepository):
    collection_name = MasterCollections.PERSONNEL
    soft_deletes = False


class TeamsRepository(BaseRepository):
    collection_name = IncidentCollections.TEAMS
    soft_deletes = False


class ResourceStatusRepository(BaseRepository):
    collection_name = IncidentCollections.RESOURCE_STATUS


def _personnel_repo() -> PersonnelRepository:
    return PersonnelRepository(get_master_db())


def _teams_repo(incident_id: str) -> TeamsRepository:
    return TeamsRepository(get_incident_db(incident_id))


def _resource_status_repo(incident_id: str) -> ResourceStatusRepository:
    return ResourceStatusRepository(get_incident_db(incident_id))


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _is_checked_in_status(status: Any) -> bool:
    return str(status or "").strip() in DERIVED_CHECKED_IN_STATUSES


def _normalize_person(doc: dict[str, Any]) -> dict[str, Any]:
    d = dict(doc)
    d.pop("_id", None)
    d["person_record"] = d.get("person_record")
    d["person_id"] = d.get("person_id") or ""
    d["primary_role"] = d.get("primary_role") or d.get("role") or d.get("rank")
    d["phone"] = d.get("phone") or d.get("contact")
    return d


def _normalize_checkin(doc: dict[str, Any]) -> dict[str, Any]:
    d = dict(doc)
    d.pop("_id", None)
    d["status"] = d.get("status") or d.get("ci_status") or d.get("planning_status") or d.get("personnel_status") or "Pending"
    d["checked_in"] = _is_checked_in_status(d["status"])
    d["checkin_status"] = "Checked In" if d["checked_in"] else "Not Checked In"
    return d


def _person_resource_status_doc(incident_id: str, person_record: int) -> dict[str, Any] | None:
    return _resource_status_repo(incident_id).find_one({
        "entity_type": "personnel",
        "record_id": person_record,
        "deleted": {"$ne": True},
    })


def _resource_status_to_checkin(doc: dict[str, Any]) -> dict[str, Any]:
    status = doc.get("status") or "Pending"
    normalized = {
        _PERSON_RECORD: doc.get("record_id"),
        "status": status,
        "ci_status": status,
        "personnel_status": "Available" if _is_checked_in_status(status) else "Pending",
        "arrival_time": doc.get("checked_in_time") or doc.get("created_at") or doc.get("updated_at") or _utcnow(),
        "location": doc.get("location") or "ICP",
        "notes": doc.get("notes"),
        "team_id": doc.get("assignment_reference"),
        "role_on_team": None,
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
        "planning_status": status,
    }
    return _normalize_checkin(normalized)


def _status_log_to_history(doc: dict[str, Any]) -> list[dict[str, Any]]:
    person_record = doc.get("record_id")
    items: list[dict[str, Any]] = []
    for entry in doc.get("status_log") or []:
        status = entry.get("status")
        ts = entry.get("timestamp") or entry.get("ts") or doc.get("updated_at") or ""
        items.append({
            _PERSON_RECORD: person_record,
            "actor": entry.get("changed_by") or "",
            "event_type": "STATUS_CHANGE",
            "ts": ts,
            "payload": {"status": status},
        })
    items.sort(key=lambda row: str(row.get("ts") or ""), reverse=True)
    return items


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
            haystack = "|".join(filter(None, [
                d.get("person_id") or "",
                d.get("name") or "",
                d.get("callsign") or "",
                d.get("phone") or "",
            ])).lower()
            if term not in haystack:
                continue
        results.append(_normalize_person(d))
        if len(results) >= limit:
            break
    return results


@router.get("/personnel/{person_record}")
def get_person_identity(incident_id: str, person_record: int) -> dict[str, Any]:
    repo = _personnel_repo()
    doc = repo.find_one({_PERSON_RECORD: person_record})
    if not doc:
        raise HTTPException(status_code=404, detail="Person not found")
    return _normalize_person(doc)


# ---------------------------------------------------------------------------
# Roster filters reference data
# ---------------------------------------------------------------------------

@router.get("/roles")
def get_distinct_roles(incident_id: str) -> list[str]:
    values: list[Any] = []
    personnel_repo = _personnel_repo()
    for field in ("primary_role", "role"):
        vals = personnel_repo._col.distinct(field, {field: {"$nin": [None, ""]}})
        values.extend(vals)
    return sorted({str(v).strip() for v in values if v})


@router.get("/teams")
def get_distinct_teams(incident_id: str) -> list[dict[str, Any]]:
    repo = _teams_repo(incident_id)
    _ensure_int_ids(repo._col)
    docs = repo.find_many({}, sort=[("name", 1)])
    result = []
    for d in docs:
        tid = d.get("int_id")
        name = d.get("name") or str(tid)
        if tid is None:
            continue
        # Response key stays "team_id" for API compatibility with existing
        # clients; the value is now the team's real identifier (int_id).
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
    """Return the personnel roster from resource_status (entity_type=personnel)."""
    from sarapp_db.mongo.collection_names import IncidentCollections
    from sarapp_db.mongo.database_manager import get_incident_db

    rs_col = get_incident_db(incident_id)[IncidentCollections.RESOURCE_STATUS]
    rs_query: dict[str, Any] = {"entity_type": "personnel", "deleted": {"$ne": True}}

    if not include_no_show:
        rs_query["status"] = {"$nin": ["Cancelled"]}

    rs_docs = list(rs_col.find(rs_query, sort=[("updated_at", -1)]))
    personnel_repo = _personnel_repo()
    result = []

    for d in rs_docs:
        prec = d.get("record_id")
        if prec is None:
            continue
        try:
            prec = int(prec)
        except (TypeError, ValueError):
            pass

        identity = personnel_repo.find_one({_PERSON_RECORD: prec}) if prec is not None else None
        if identity is None and prec is not None:
            identity = {_PERSON_RECORD: prec, "name": str(prec)}

        name = d.get("resource_name") or (identity or {}).get("name") or str(prec or "")
        visible_id = (identity or {}).get("person_id") or ""
        callsign = (identity or {}).get("callsign") or ""
        phone = (identity or {}).get("phone") or ""

        if q:
            t = q.strip().lower()
            haystack = "|".join(filter(None, [visible_id, name, callsign, phone])).lower()
            if t not in haystack:
                continue

        row_status = d.get("status") or "Pending"
        assigned_to = d.get("assigned_to")

        if ci_status and ci_status not in ("All", ""):
            # Map legacy check-in status values to resource_status canonical values
            _ci_map = {"CheckedIn": "Checked In"}
            canonical = _ci_map.get(ci_status, ci_status)
            if row_status != canonical:
                continue

        if role and role != "All":
            row_role = (identity or {}).get("primary_role") or (identity or {}).get("role")
            if row_role != role:
                continue

        if team and team not in ("All", "—", ""):
            if not assigned_to or team.lower() not in str(assigned_to).lower():
                continue

        is_demob = row_status == "Demobilized"
        is_not_coming = row_status == "Cancelled"

        result.append({
            _PERSON_RECORD: prec,
            "person_id": visible_id,
            "name": name,
            "role": (identity or {}).get("primary_role") or (identity or {}).get("role"),
            "team": assigned_to or "—",
            "team_id": None,
            "phone": phone,
            "callsign": callsign,
            "status": row_status,
            "ci_status": "CheckedIn" if row_status == "Checked In" else row_status,
            "checked_in": _is_checked_in_status(row_status),
            "updated_at": d.get("updated_at"),
            "row_class": "row-demob" if is_demob else None,
            "ui_flags": {
                "hidden_by_default": is_not_coming,
                "grayed": is_demob,
            },
        })

    result.sort(key=lambda r: (r.get("name") or "").lower())
    return result


# ---------------------------------------------------------------------------
# Check-in record CRUD
# ---------------------------------------------------------------------------

@router.get("/{person_record}")
def fetch_checkin(incident_id: str, person_record: int) -> dict[str, Any]:
    doc = _person_resource_status_doc(incident_id, person_record)
    if not doc:
        raise HTTPException(status_code=404, detail="Check-in record not found")
    return _resource_status_to_checkin(doc)


@router.put("/{person_record}")
def save_checkin(
    incident_id: str, person_record: int, body: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    repo = _resource_status_repo(incident_id)
    logger.info(
        "checkin save start incident_id=%s person_record=%s body_keys=%s",
        incident_id,
        person_record,
        sorted(body.keys()),
    )
    body.pop("_id", None)
    body[_PERSON_RECORD] = person_record

    if body.get("team_id") in ("—", ""):
        body["team_id"] = None

    existing = _person_resource_status_doc(incident_id, person_record)
    status = body.get("status") or body.get("ci_status") or body.get("planning_status") or "Pending"
    now = _utcnow()
    resource_doc = {
        "entity_type": "personnel",
        "record_id": person_record,
        "resource_id": str(person_record),
        "resource_name": str(person_record),
        "resource_type": "Personnel",
        "status": status,
        "assigned_to": body.get("team_id"),
        "assignment_reference": body.get("team_id"),
        "location": body.get("location"),
        "notes": body.get("notes"),
        "checked_in_time": body.get("arrival_time"),
        "updated_at": now,
    }
    if existing:
        logger.info(
            "checkin save updating incident_id=%s person_record=%s existing_id=%s",
            incident_id,
            person_record,
            existing.get("_id"),
        )
        updates = dict(resource_doc)
        if status != existing.get("status"):
            repo.apply_update(
                existing["_id"],
                {
                    "$set": updates,
                    "$push": {"status_log": {"status": status, "timestamp": now, "changed_by": "Check-In"}},
                },
            )
        else:
            repo.update_one(existing["_id"], updates)
        doc = repo.find_by_id(existing["_id"])
    else:
        logger.info(
            "checkin save inserting incident_id=%s person_record=%s",
            incident_id,
            person_record,
        )
        resource_doc["created_at"] = now
        resource_doc["status_log"] = [{"status": status, "timestamp": now, "changed_by": "Check-In"}]
        doc = repo.insert_one(resource_doc)

    # Mirror contact fields back to master personnel and keep incident_personnel in sync.
    try:
        personnel_repo = _personnel_repo()
        ident = personnel_repo.find_one({_PERSON_RECORD: person_record})
        if ident:
            if ident.get("name"):
                repo.update_one(doc["_id"], {"resource_name": ident["name"], "resource_id": ident.get("person_id") or str(person_record)})
                doc = repo.find_by_id(doc["_id"])
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
                logger.info(
                    "checkin save mirrored personnel fields incident_id=%s person_record=%s update_keys=%s",
                    incident_id,
                    person_record,
                    sorted(updates.keys()),
                )

            from sarapp_db.mongo.client import get_db
            incident_personnel_col = get_db(f"sarapp_incident_{incident_id}")["incident_personnel"]
            copy_fields = {
                _PERSON_RECORD: person_record,
                "incident_id": incident_id,
                "name": ident.get("name"),
                "rank": ident.get("rank"),
                "callsign": updates.get("callsign", ident.get("callsign")),
                "role": updates.get("primary_role", ident.get("primary_role") or ident.get("role")),
                "phone": updates.get("phone", ident.get("phone")),
                "email": ident.get("email"),
                "organization": ident.get("organization"),
                "person_id": ident.get("person_id") or "",
                "is_medic": bool(ident.get("is_medic", False)),
            }
            incident_personnel_col.update_one(
                {_PERSON_RECORD: person_record}, {"$set": copy_fields}, upsert=True
            )
            logger.info(
                "checkin save upserted incident_personnel incident_id=%s person_record=%s",
                incident_id,
                person_record,
            )
    except Exception:
        logger.exception(
            "checkin save mirror failed incident_id=%s person_record=%s",
            incident_id,
            person_record,
        )
        pass

    logger.info(
        "checkin save complete incident_id=%s person_record=%s doc_keys=%s",
        incident_id,
        person_record,
        sorted(doc.keys()) if isinstance(doc, dict) else None,
    )
    return _resource_status_to_checkin(doc)


# ---------------------------------------------------------------------------
# Team check-in / disband (ICS-211 workflow)
# ---------------------------------------------------------------------------

def _find_team_by_int_id(teams_repo: "TeamsRepository", team_id: str) -> dict[str, Any]:
    """Resolve the `{team_id}` path segment (the team's int_id) to its document.

    The path segment is still named `team_id` for URL-compatibility with
    existing callers, but teams are identified by `int_id` — see the
    field-dashboard/team-id consolidation notes.
    """
    _ensure_int_ids(teams_repo._col)
    try:
        int_id = int(team_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=404, detail="Team not found") from None
    team_doc = teams_repo.find_one({"int_id": int_id})
    if not team_doc:
        raise HTTPException(status_code=404, detail="Team not found")
    return team_doc


@router.post("/teams/{team_id}/checkin")
def team_checkin(
    incident_id: str, team_id: str, body: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    """Check in a team and optionally its assets."""
    teams_repo = _teams_repo(incident_id)
    team_doc = _find_team_by_int_id(teams_repo, team_id)

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

    updated = teams_repo.find_by_id(team_doc["_id"])
    updated.pop("_id", None)
    return updated


@router.post("/teams/{team_id}/disband")
def team_disband(
    incident_id: str, team_id: str, body: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    """Disband a team (separate from check-in)."""
    teams_repo = _teams_repo(incident_id)
    team_doc = _find_team_by_int_id(teams_repo, team_id)

    now = _utcnow()
    disbanded_by = body.get("disbanded_by")

    updates = {
        "disbanded": True,
        "disbanded_at": now,
        "disbanded_by": disbanded_by,
    }
    teams_repo.update_one(team_doc["_id"], updates)

    updated = teams_repo.find_by_id(team_doc["_id"])
    updated.pop("_id", None)
    return updated


@router.get("/teams/checked-state")
def list_teams_by_checkin_state(
    incident_id: str,
    checked_in: bool = Query(False),
    include_disbanded: bool = Query(False),
) -> list[dict[str, Any]]:
    repo = _teams_repo(incident_id)
    _ensure_int_ids(repo._col)
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
    repo = _resource_status_repo(incident_id)
    planning_stati = ["Requested", "Ordered", "Enroute", "Available", "Assigned", "Cancelled", "Pending", "Staged"]
    clause: dict[str, Any] = {"$in": planning_stati}
    if status and status in planning_stati:
        clause = status
    query: dict[str, Any] = {"entity_type": "personnel", "status": clause, "deleted": {"$ne": True}}
    docs = repo.find_many(query, sort=[("updated_at", -1)])
    result = []
    for d in docs:
        result.append(_resource_status_to_checkin(d))
    return result


@router.patch("/{person_record}")
def patch_checkin(
    incident_id: str, person_record: int, body: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    repo = _resource_status_repo(incident_id)
    existing = _person_resource_status_doc(incident_id, person_record)
    if not existing:
        raise HTTPException(status_code=404, detail="Check-in record not found")
    patch = {k: v for k, v in body.items() if k not in ("_id", _PERSON_RECORD)}
    if not patch:
        raise HTTPException(status_code=400, detail="No updatable fields provided")
    updates: dict[str, Any] = {"updated_at": _utcnow()}
    field_map = {
        "status": "status",
        "ci_status": "status",
        "planning_status": "status",
        "arrival_time": "checked_in_time",
        "location": "location",
        "notes": "notes",
        "team_id": "assignment_reference",
    }
    for src, dst in field_map.items():
        if src in patch:
            updates[dst] = patch[src]
    repo.update_one(existing["_id"], updates)
    doc = repo.find_by_id(existing["_id"])
    return _resource_status_to_checkin(doc)


@router.patch("/{person_record}/status")
def patch_checkin_status(
    incident_id: str, person_record: int, body: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    repo = _resource_status_repo(incident_id)
    logger.info(
        "checkin status patch start incident_id=%s person_record=%s body_keys=%s",
        incident_id,
        person_record,
        sorted(body.keys()),
    )
    existing = _person_resource_status_doc(incident_id, person_record)
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

    now = _utcnow()
    patch["updated_at"] = now
    repo.apply_update(
        existing["_id"],
        {
            "$set": patch,
            "$push": {"status_log": {"status": patch["status"], "timestamp": now, "changed_by": "Check-In"}},
        },
    )
    doc = repo.find_by_id(existing["_id"])

    if patch.get("status") == "Demobilized":
        # Auto-stop location tracking the moment a tracking person leaves
        # field-active status, without waiting for the mobile device to say
        # so (IC staff may demobilize someone while their phone is still
        # pinging). Same "clear, don't fall back to another member" behavior
        # as the mobile-initiated stop endpoint — see mobile_location.py.
        teams_repo = _teams_repo(incident_id)
        team_doc = teams_repo.find_one({"current_location_person_record": person_record})
        if team_doc:
            teams_repo.update_one(
                team_doc["_id"],
                {
                    "current_location_lat": None,
                    "current_location_lon": None,
                    "current_location_updated_at": None,
                    "current_location_person_record": None,
                },
            )

    logger.info(
        "checkin status patch complete incident_id=%s person_record=%s status=%s",
        incident_id,
        person_record,
        patch.get("status"),
    )
    return _resource_status_to_checkin(doc)


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

@router.post("/history")
def log_history(
    incident_id: str, body: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    person_record = body.get(_PERSON_RECORD)
    if person_record is None:
        raise HTTPException(status_code=400, detail="person_record is required")
    person_record = int(person_record)
    repo = _resource_status_repo(incident_id)
    doc = _person_resource_status_doc(incident_id, person_record)
    if not doc:
        raise HTTPException(status_code=404, detail="Check-in record not found")
    entry = {
        "status": (body.get("payload") or {}).get("status") or doc.get("status") or "Pending",
        "timestamp": body.get("ts") or _utcnow(),
        "changed_by": body.get("actor") or "",
        "event_type": body.get("event_type") or "NOTE",
        "payload": body.get("payload") or {},
    }
    repo.apply_update(doc["_id"], {"$push": {"status_log": entry}, "$set": {"updated_at": entry["timestamp"]}})
    return {
        _PERSON_RECORD: person_record,
        "actor": entry["changed_by"],
        "event_type": entry["event_type"],
        "ts": entry["timestamp"],
        "payload": entry["payload"],
    }


@router.get("/history/{person_record}")
def list_history(incident_id: str, person_record: int) -> list[dict[str, Any]]:
    doc = _person_resource_status_doc(incident_id, person_record)
    if not doc:
        return []
    return _status_log_to_history(doc)
