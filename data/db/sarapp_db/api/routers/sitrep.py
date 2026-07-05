"""FastAPI router for the SITREP (Situation Report) module."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from sarapp_db.mongo.client import get_db
from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()

_MVP_SECTIONS = [
    "situation_overview",
    "operational_status",
    "significant_changes",
    "safety_hazards",
    "resource_status",
    "communications_status",
    "liaison_coordination",
    "needs_decisions",
    "next_update",
]

_SECTION_TITLES = {
    "situation_overview": "Situation Overview",
    "operational_status": "Operational Status",
    "significant_changes": "Significant Changes",
    "safety_hazards": "Safety / Hazards",
    "resource_status": "Resource Status",
    "communications_status": "Communications Status",
    "liaison_coordination": "Liaison / Agency Coordination",
    "needs_decisions": "Needs / Decisions",
    "next_update": "Next Update",
}


class SitrepRepository(BaseRepository):
    collection_name = IncidentCollections.SITREPS


class SitrepEventsRepository(BaseRepository):
    collection_name = IncidentCollections.SITREP_EVENTS


class SitrepDistributionsRepository(BaseRepository):
    collection_name = IncidentCollections.SITREP_DISTRIBUTIONS
    soft_deletes = False


def _sitrep_repo(incident_id: str) -> SitrepRepository:
    return SitrepRepository(get_db(f"sarapp_incident_{incident_id}"))


def _events_repo(incident_id: str) -> SitrepEventsRepository:
    return SitrepEventsRepository(get_db(f"sarapp_incident_{incident_id}"))


def _distributions_repo(incident_id: str) -> SitrepDistributionsRepository:
    return SitrepDistributionsRepository(get_db(f"sarapp_incident_{incident_id}"))


def _raw_col(incident_id: str, name: str):
    return get_db(f"sarapp_incident_{incident_id}")[name]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid.uuid4().hex


def _next_sitrep_number(incident_id: str) -> int:
    col = _raw_col(incident_id, IncidentCollections.SITREPS)
    last = col.find_one(
        {"incident_id": incident_id, "deleted": {"$ne": True}},
        sort=[("sitrep_number", -1)],
        projection={"sitrep_number": 1},
    )
    if last is not None and isinstance(last.get("sitrep_number"), int):
        return last["sitrep_number"] + 1
    return 1


def _default_sections() -> list[dict]:
    return [
        {
            "section_type": stype,
            "title": _SECTION_TITLES[stype],
            "auto_content": "",
            "edited_content": "",
            "visibility": "internal",
            "review_status": "auto_filled",
            "last_refreshed_at": None,
        }
        for stype in _MVP_SECTIONS
    ]


def _strip_mongo(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


# ---------------------------------------------------------------------------
# SITREP CRUD
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/sitreps")
def list_sitreps(incident_id: str) -> list[dict]:
    col = _raw_col(incident_id, IncidentCollections.SITREPS)
    docs = col.find(
        {"incident_id": incident_id, "deleted": {"$ne": True}},
        sort=[("sitrep_number", -1)],
    )
    return [_strip_mongo(d) for d in docs]


@router.post("/incidents/{incident_id}/sitreps", status_code=201)
def create_sitrep(incident_id: str, body: dict) -> dict:
    repo = _sitrep_repo(incident_id)
    number = _next_sitrep_number(incident_id)
    now = _now()
    doc = {
        "id": _new_id(),
        "incident_id": incident_id,
        "sitrep_number": number,
        "operational_period_id": body.get("operational_period_id"),
        "created_at": now,
        "updated_at": now,
        "prepared_by": body.get("prepared_by", ""),
        "status": "draft",
        "audience": body.get("audience", "internal"),
        "approved_by": None,
        "approved_at": None,
        "distributed_at": None,
        "summary": body.get("summary", ""),
        "current_priority": body.get("current_priority", ""),
        "current_tempo": body.get("current_tempo", "stable"),
        "next_update_due": body.get("next_update_due"),
        "sections": body.get("sections") or _default_sections(),
        "deleted": False,
    }
    repo.insert_one(doc)
    return _strip_mongo(doc)


_TASK_STATUS_NORM: dict[str, str] = {
    "draft": "draft", "created": "draft", "pending": "draft",
    "planned": "planned",
    "assigned": "assigned",
    "in progress": "in_progress", "in_progress": "in_progress", "progress": "in_progress",
    "complete": "complete", "completed": "complete", "closed": "complete",
    "blocked": "blocked", "delayed": "blocked",
    "suspended": "suspended",
    "cancelled": "cancelled", "canceled": "cancelled",
}

_TEAM_STATUS_NORM: dict[str, str] = {
    "available": "available", "avail": "available", "free": "available", "unassigned": "available",
    "assigned": "active", "in field": "active", "on scene": "active",
    "en route": "enroute", "enroute": "enroute",
    "rtb": "returning", "returning": "returning",
    "out of service": "out_of_service", "oos": "out_of_service",
    "overdue": "overdue",
}


@router.get("/incidents/{incident_id}/sitreps/operational-summary")
def get_operational_summary(incident_id: str) -> dict:
    """Return live counts pulled from operations, tasks, teams, and checklists."""
    db = get_db(f"sarapp_incident_{incident_id}")

    # Tasks — fetch all and normalize status in Python.
    # Tasks live in the per-incident DB so no incident_id field filter is needed;
    # status values are stored in mixed case (e.g. "In Progress", "Draft").
    tasks_col = db[IncidentCollections.TASKS]
    task_counts: dict[str, int] = {
        "draft": 0, "planned": 0, "assigned": 0, "in_progress": 0,
        "complete": 0, "blocked": 0, "suspended": 0, "cancelled": 0,
    }
    for doc in tasks_col.find({"deleted": {"$ne": True}}, projection={"status": 1}):
        key = _TASK_STATUS_NORM.get(str(doc.get("status") or "").strip().lower(), "draft")
        task_counts[key] = task_counts.get(key, 0) + 1

    # Teams — same approach; status stored as title-case display values.
    teams_col = db[IncidentCollections.TEAMS]
    team_counts: dict[str, int] = {
        "active": 0, "available": 0, "enroute": 0, "returning": 0,
        "out_of_service": 0, "overdue": 0,
    }
    for doc in teams_col.find({"deleted": {"$ne": True}}, projection={"status": 1}):
        key = _TEAM_STATUS_NORM.get(str(doc.get("status") or "").strip().lower(), "available")
        team_counts[key] = team_counts.get(key, 0) + 1

    # Check-in counts — no incident_id filter; collection is scoped to the incident DB.
    checkin_col = db[IncidentCollections.CHECK_IN_OUT]
    total_checked_in = checkin_col.count_documents(
        {"status": "checked_in", "resource_type": "personnel"}
    )

    alerts: list[dict] = []
    overdue_teams = team_counts.get("overdue", 0)
    if overdue_teams:
        alerts.append({"message": f"{overdue_teams} team(s) overdue", "source": "Operations"})

    in_progress = task_counts.get("in_progress", 0)
    if in_progress:
        alerts.append({"message": f"{in_progress} task(s) in progress", "source": "Operations"})

    # Weather advisories are cached on the config doc by the weather module
    # (see modules/intel/weather/services/api_link.py -> weather_payload.advisories).
    weather_col = db[IncidentCollections.WEATHER_DATA]
    weather_cfg = weather_col.find_one({"key": "config"}, projection={"weather_payload.advisories": 1})
    advisories = ((weather_cfg or {}).get("weather_payload") or {}).get("advisories") or []
    if len(advisories) == 1:
        event = advisories[0].get("event") or "advisory"
        alerts.append({"message": f"Weather advisory active: {event}", "source": "Weather"})
    elif advisories:
        alerts.append({"message": f"{len(advisories)} weather advisories active", "source": "Weather"})

    return {
        "teams": team_counts,
        "tasks": task_counts,
        "total_checked_in": total_checked_in,
        "alerts": alerts,
    }


@router.get("/incidents/{incident_id}/sitreps/{sitrep_id}")
def get_sitrep(incident_id: str, sitrep_id: str) -> dict:
    col = _raw_col(incident_id, IncidentCollections.SITREPS)
    doc = col.find_one({"id": sitrep_id, "incident_id": incident_id})
    if not doc or doc.get("deleted"):
        raise HTTPException(status_code=404, detail="SITREP not found")
    return _strip_mongo(doc)


@router.patch("/incidents/{incident_id}/sitreps/{sitrep_id}")
def update_sitrep(incident_id: str, sitrep_id: str, body: dict) -> dict:
    repo = _sitrep_repo(incident_id)
    col = _raw_col(incident_id, IncidentCollections.SITREPS)
    doc = col.find_one({"id": sitrep_id, "incident_id": incident_id})
    if not doc or doc.get("deleted"):
        raise HTTPException(status_code=404, detail="SITREP not found")

    allowed = {
        "prepared_by", "status", "audience", "approved_by", "approved_at",
        "distributed_at", "summary", "current_priority", "current_tempo",
        "next_update_due", "sections", "operational_period_id",
    }
    updates: dict[str, Any] = {k: v for k, v in body.items() if k in allowed}
    updates["updated_at"] = _now()

    if updates:
        repo.apply_update(doc["_id"], {"$set": updates})

    updated = col.find_one({"id": sitrep_id})
    return _strip_mongo(updated)


@router.delete("/incidents/{incident_id}/sitreps/{sitrep_id}", status_code=204)
def delete_sitrep(incident_id: str, sitrep_id: str) -> None:
    repo = _sitrep_repo(incident_id)
    col = _raw_col(incident_id, IncidentCollections.SITREPS)
    doc = col.find_one({"id": sitrep_id, "incident_id": incident_id})
    if not doc or doc.get("deleted"):
        raise HTTPException(status_code=404, detail="SITREP not found")
    repo.apply_update(doc["_id"], {"$set": {"deleted": True, "updated_at": _now()}})


@router.post("/incidents/{incident_id}/sitreps/{sitrep_id}/duplicate", status_code=201)
def duplicate_sitrep(incident_id: str, sitrep_id: str, body: Optional[dict] = None) -> dict:
    """Create a new SITREP pre-filled from an existing one (fast next-update flow)."""
    col = _raw_col(incident_id, IncidentCollections.SITREPS)
    source = col.find_one({"id": sitrep_id, "incident_id": incident_id})
    if not source or source.get("deleted"):
        raise HTTPException(status_code=404, detail="Source SITREP not found")

    repo = _sitrep_repo(incident_id)
    number = _next_sitrep_number(incident_id)
    now = _now()
    extra = body or {}

    sections = []
    for s in source.get("sections", _default_sections()):
        sections.append({
            **s,
            "auto_content": s.get("edited_content") or s.get("auto_content", ""),
            "review_status": "auto_filled",
            "last_refreshed_at": None,
        })

    doc = {
        "id": _new_id(),
        "incident_id": incident_id,
        "sitrep_number": number,
        "operational_period_id": extra.get("operational_period_id", source.get("operational_period_id")),
        "created_at": now,
        "updated_at": now,
        "prepared_by": extra.get("prepared_by", source.get("prepared_by", "")),
        "status": "draft",
        "audience": extra.get("audience", source.get("audience", "internal")),
        "approved_by": None,
        "approved_at": None,
        "distributed_at": None,
        "summary": "",
        "current_priority": source.get("current_priority", ""),
        "current_tempo": source.get("current_tempo", "stable"),
        "next_update_due": extra.get("next_update_due"),
        "sections": sections,
        "deleted": False,
    }
    repo.insert_one(doc)
    return _strip_mongo(doc)


@router.post("/incidents/{incident_id}/sitreps/{sitrep_id}/refresh")
def refresh_sitrep(incident_id: str, sitrep_id: str) -> dict:
    """Re-pull live module data into the SITREP's auto-filled section content."""
    col = _raw_col(incident_id, IncidentCollections.SITREPS)
    doc = col.find_one({"id": sitrep_id, "incident_id": incident_id})
    if not doc or doc.get("deleted"):
        raise HTTPException(status_code=404, detail="SITREP not found")

    summary = get_operational_summary(incident_id)
    teams = summary["teams"]
    tasks = summary["tasks"]
    alerts = summary["alerts"]
    now = _now()
    now_hhmm = now[:16].replace("T", " ")

    ops_lines = [
        f"As of {now_hhmm}, {teams['active']} team(s) are active, "
        f"{teams['available']} available, {teams['enroute']} enroute, "
        f"{teams['returning']} returning.",
        f"Tasks: {tasks['in_progress']} in progress, {tasks['assigned']} assigned, "
        f"{tasks['planned']} planned, {tasks['complete']} completed.",
    ]
    if tasks["blocked"]:
        ops_lines.append(f"{tasks['blocked']} task(s) blocked.")
    if tasks["suspended"]:
        ops_lines.append(f"{tasks['suspended']} task(s) suspended.")

    resource_lines = [
        f"Personnel checked in: {summary['total_checked_in']}.",
        f"Teams — active: {teams['active']}, available: {teams['available']}, "
        f"enroute: {teams['enroute']}, returning: {teams['returning']}, "
        f"out of service: {teams['out_of_service']}.",
    ]

    if alerts:
        safety_text = "\n".join(
            f"- {a['message']} [{a.get('source', '')}]" for a in alerts
        )
    else:
        safety_text = "No active alerts reported by modules."

    auto_by_section = {
        "operational_status": " ".join(ops_lines),
        "resource_status": " ".join(resource_lines),
        "safety_hazards": safety_text,
    }

    sections = []
    for s in doc.get("sections", _default_sections()):
        stype = s.get("section_type")
        if stype in auto_by_section:
            s = {**s, "auto_content": auto_by_section[stype], "last_refreshed_at": now}
        sections.append(s)

    repo = _sitrep_repo(incident_id)
    repo.apply_update(doc["_id"], {"$set": {"sections": sections, "updated_at": now}})
    updated = col.find_one({"id": sitrep_id})
    return _strip_mongo(updated)


# ---------------------------------------------------------------------------
# SITREP Events
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/sitrep-events")
def list_events(incident_id: str, sitrep_id: Optional[str] = None) -> list[dict]:
    col = _raw_col(incident_id, IncidentCollections.SITREP_EVENTS)
    query: dict[str, Any] = {"incident_id": incident_id, "deleted": {"$ne": True}}
    if sitrep_id:
        query["sitrep_id"] = sitrep_id
    docs = col.find(query, sort=[("timestamp", -1)])
    return [_strip_mongo(d) for d in docs]


@router.post("/incidents/{incident_id}/sitrep-events", status_code=201)
def create_event(incident_id: str, body: dict) -> dict:
    repo = _events_repo(incident_id)
    now = _now()
    doc = {
        "id": _new_id(),
        "incident_id": incident_id,
        "sitrep_id": body.get("sitrep_id"),
        "timestamp": body.get("timestamp", now),
        "event_type": body.get("event_type", ""),
        "summary": body.get("summary", ""),
        "source": body.get("source", ""),
        "impact": body.get("impact", "low"),
        "visibility": body.get("visibility", "internal"),
        "include_in_sitrep": body.get("include_in_sitrep", True),
        "include_in_214": body.get("include_in_214", False),
        "reviewed_by": body.get("reviewed_by"),
        "notes": body.get("notes", ""),
        "created_at": now,
        "updated_at": now,
        "deleted": False,
    }
    repo.insert_one(doc)
    return _strip_mongo(doc)


@router.patch("/incidents/{incident_id}/sitrep-events/{event_id}")
def update_event(incident_id: str, event_id: str, body: dict) -> dict:
    repo = _events_repo(incident_id)
    col = _raw_col(incident_id, IncidentCollections.SITREP_EVENTS)
    doc = col.find_one({"id": event_id, "incident_id": incident_id})
    if not doc or doc.get("deleted"):
        raise HTTPException(status_code=404, detail="Event not found")
    allowed = {
        "timestamp", "event_type", "summary", "source", "impact",
        "visibility", "include_in_sitrep", "include_in_214", "reviewed_by", "notes", "sitrep_id",
    }
    updates = {k: v for k, v in body.items() if k in allowed}
    updates["updated_at"] = _now()
    if updates:
        repo.apply_update(doc["_id"], {"$set": updates})
    updated = col.find_one({"id": event_id})
    return _strip_mongo(updated)


@router.delete("/incidents/{incident_id}/sitrep-events/{event_id}", status_code=204)
def delete_event(incident_id: str, event_id: str) -> None:
    repo = _events_repo(incident_id)
    col = _raw_col(incident_id, IncidentCollections.SITREP_EVENTS)
    doc = col.find_one({"id": event_id, "incident_id": incident_id})
    if not doc or doc.get("deleted"):
        raise HTTPException(status_code=404, detail="Event not found")
    repo.apply_update(doc["_id"], {"$set": {"deleted": True, "updated_at": _now()}})


# ---------------------------------------------------------------------------
# SITREP Distributions
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/sitreps/{sitrep_id}/distributions")
def list_distributions(incident_id: str, sitrep_id: str) -> list[dict]:
    col = _raw_col(incident_id, IncidentCollections.SITREP_DISTRIBUTIONS)
    docs = col.find({"sitrep_id": sitrep_id}, sort=[("distributed_at", -1)])
    return [_strip_mongo(d) for d in docs]


@router.post("/incidents/{incident_id}/sitreps/{sitrep_id}/distributions", status_code=201)
def create_distribution(incident_id: str, sitrep_id: str, body: dict) -> dict:
    sitrep_col = _raw_col(incident_id, IncidentCollections.SITREPS)
    sitrep = sitrep_col.find_one({"id": sitrep_id, "incident_id": incident_id})
    if not sitrep or sitrep.get("deleted"):
        raise HTTPException(status_code=404, detail="SITREP not found")

    repo = _distributions_repo(incident_id)
    now = _now()
    doc = {
        "id": _new_id(),
        "sitrep_id": sitrep_id,
        "incident_id": incident_id,
        "version_name": body.get("version_name", ""),
        "audience": body.get("audience", "internal"),
        "recipient_group": body.get("recipient_group", ""),
        "delivery_method": body.get("delivery_method", "print"),
        "approved_by": body.get("approved_by"),
        "distributed_by": body.get("distributed_by", ""),
        "distributed_at": body.get("distributed_at", now),
        "export_file_path": body.get("export_file_path"),
        "notes": body.get("notes", ""),
        "created_at": now,
    }
    repo.insert_one(doc)
    return _strip_mongo(doc)
