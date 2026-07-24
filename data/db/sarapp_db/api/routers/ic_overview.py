"""FastAPI router — IC overview endpoints for the active incident."""
from __future__ import annotations

import logging
import uuid
from collections import Counter
from datetime import datetime
from typing import Any, Dict, Optional

from dateutil import parser as dateutil_parser
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sarapp_db.mongo.database_manager import get_incident_db, get_system_db
from sarapp_db.mongo.collection_names import IncidentCollections, SystemCollections
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


class SystemIncidentsRepository(BaseRepository):
    collection_name = SystemCollections.INCIDENTS
    soft_deletes = False


class IncidentProfileRepository(BaseRepository):
    collection_name = IncidentCollections.INCIDENT_PROFILE
    soft_deletes = False


class TeamsRepository(BaseRepository):
    collection_name = IncidentCollections.TEAMS
    soft_deletes = False


class TasksRepository(BaseRepository):
    collection_name = IncidentCollections.TASKS
    soft_deletes = False


class IncidentChannelsRepository(BaseRepository):
    collection_name = IncidentCollections.INCIDENT_CHANNELS
    soft_deletes = False


class ResourceRequestsRepository(BaseRepository):
    collection_name = IncidentCollections.RESOURCE_REQUESTS
    soft_deletes = False


class OperationalPeriodsRepository(BaseRepository):
    collection_name = IncidentCollections.OPERATIONAL_PERIODS
    soft_deletes = False


class FacilitiesRepository(BaseRepository):
    collection_name = IncidentCollections.FACILITIES


def _system_incidents_repo() -> SystemIncidentsRepository:
    return SystemIncidentsRepository(get_system_db())


def _profile_repo(incident_id: str) -> IncidentProfileRepository:
    return IncidentProfileRepository(get_incident_db(incident_id))


def _teams_repo(incident_id: str) -> TeamsRepository:
    return TeamsRepository(get_incident_db(incident_id))


def _tasks_repo(incident_id: str) -> TasksRepository:
    return TasksRepository(get_incident_db(incident_id))


def _channels_repo(incident_id: str) -> IncidentChannelsRepository:
    return IncidentChannelsRepository(get_incident_db(incident_id))


def _resource_requests_repo(incident_id: str) -> ResourceRequestsRepository:
    return ResourceRequestsRepository(get_incident_db(incident_id))


def _op_periods_repo(incident_id: str) -> OperationalPeriodsRepository:
    return OperationalPeriodsRepository(get_incident_db(incident_id))


def _facilities_repo(incident_id: str) -> FacilitiesRepository:
    return FacilitiesRepository(get_incident_db(incident_id))


def _utcnow() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Incident registry — list and create
# ---------------------------------------------------------------------------

@router.get("")
def list_incidents(status: str = "", number: str = "") -> list[dict[str, Any]]:
    repo = _system_incidents_repo()
    query: dict[str, Any] = {}
    if status:
        query["status"] = {"$regex": status, "$options": "i"}
    if number:
        query["number"] = number
    docs = repo.find_many(query, sort=[("created_at", -1)])
    result = []
    for doc in docs:
        doc.pop("_id", None)
        doc["id"] = str(doc.get("incident_id") or doc.get("id") or "")
        result.append(doc)
    return result


class CreateIncidentRequest(BaseModel):
    number: str
    name: str
    type: str = ""
    description: str = ""
    icp_location: str = ""
    icp_facility_id: Optional[str] = None
    is_training: bool = False
    # Creating user's saved Weather Thresholds defaults (see
    # ui/settings/pages/weather_defaults_page.py); if omitted, the initial
    # weather_config document falls back to hardcoded thresholds.
    weather_thresholds: Optional[Dict[str, Any]] = None


def _seed_weather_config(incident_id: str, weather_thresholds: Optional[Dict[str, Any]]) -> None:
    """Insert the incident's initial weather_config, seeded from the creating
    user's saved Weather Thresholds defaults if provided, otherwise the
    router's own hardcoded defaults (see routers/weather.py WeatherThresholds)."""
    try:
        from sarapp_db.api.routers.weather import WeatherConfigRepository, WeatherThresholds

        repo = WeatherConfigRepository(get_incident_db(incident_id))
        thresholds = WeatherThresholds(**weather_thresholds) if weather_thresholds else WeatherThresholds()
        repo.insert_one(
            {
                "incident_id": incident_id,
                "polling_minutes": 10,
                "locations": [],
                "thresholds": thresholds.model_dump(),
            }
        )
    except Exception:
        logging.getLogger(__name__).exception("Failed to seed weather_config for incident %s", incident_id)


@router.post("", status_code=201)
def create_incident(body: CreateIncidentRequest) -> dict[str, Any]:
    sys_repo = _system_incidents_repo()
    if sys_repo.find_one({"number": body.number}):
        raise HTTPException(409, f"Incident with number '{body.number}' already exists")
    incident_id = str(uuid.uuid4())
    registry_fields = {
        "_id": incident_id,
        "incident_id": incident_id,
        "number": body.number,
        "name": body.name,
        "type": body.type,
        "description": body.description,
        "icp_location": body.icp_location,
        "icp_facility_id": body.icp_facility_id,
        "is_training": body.is_training,
        "status": "active",
    }
    registry_doc = sys_repo.insert_one(registry_fields)

    now = registry_doc.get("created_at") or _utcnow()
    profile_doc = {
        "incident_id": incident_id,
        "incident_number": body.number,
        "name": body.name,
        "incident_type": body.type,
        "description": body.description,
        "icp_address": body.icp_location,
        "icp_facility_id": body.icp_facility_id,
        "is_training": body.is_training,
        "status": "active",
        "start_time": now,
    }
    profile_repo = IncidentProfileRepository(get_incident_db(incident_id))
    profile_repo.insert_one(profile_doc)

    _seed_weather_config(incident_id, body.weather_thresholds)

    registry_doc.pop("_id", None)
    registry_doc["id"] = incident_id
    return registry_doc


# ---------------------------------------------------------------------------
# Incident profile
# ---------------------------------------------------------------------------

def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return dateutil_parser.parse(str(value))
    except (ValueError, OverflowError, TypeError):
        return None


@router.get("/{incident_id}/profile")
def get_profile(incident_id: str) -> dict[str, Any]:
    repo = _profile_repo(incident_id)
    doc = repo.find_one({"incident_id": incident_id})
    if not doc:
        raise HTTPException(404, f"Incident '{incident_id}' not found")
    status = doc.get("status") or ""
    return {
        "id": incident_id,
        "name": doc.get("name", ""),
        "number": doc.get("incident_number", incident_id),
        "type": doc.get("incident_type", ""),
        "status": status[:1].upper() + status[1:] if status else "",
        "description": doc.get("description", ""),
        "start_time": doc.get("start_time") or doc.get("created_at") or "",
        "end_time": doc.get("end_time") or "",
        "icp_location": doc.get("icp_address") or doc.get("icp_location") or "",
        "icp_facility_id": doc.get("icp_facility_id") or "",
        "latitude": doc.get("latitude"),
        "longitude": doc.get("longitude"),
        "is_training": bool(doc.get("is_training", False)),
    }


class PatchProfileRequest(BaseModel):
    name: Optional[str] = None
    number: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    icp_location: Optional[str] = None
    icp_facility_id: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_training: Optional[bool] = None


_PROFILE_FIELD_MAP = {
    "name": "name",
    "number": "incident_number",
    "type": "incident_type",
    "description": "description",
    "start_time": "start_time",
    "end_time": "end_time",
    "icp_location": "icp_address",
    "icp_facility_id": "icp_facility_id",
    "is_training": "is_training",
}


@router.patch("/{incident_id}/profile")
def patch_profile(incident_id: str, body: PatchProfileRequest) -> dict[str, Any]:
    repo = _profile_repo(incident_id)
    data = body.model_dump(exclude_none=True)
    update: dict[str, Any] = {}
    for api_field, mongo_field in _PROFILE_FIELD_MAP.items():
        if api_field in data:
            update[mongo_field] = data[api_field]
    if "status" in data:
        update["status"] = (data["status"] or "").lower()
    facility_doc: Optional[dict[str, Any]] = None
    if "icp_facility_id" in data and data["icp_facility_id"]:
        facility_doc = _facilities_repo(incident_id).find_by_id(str(data["icp_facility_id"]))
        if not facility_doc:
            raise HTTPException(404, f"Facility '{data['icp_facility_id']}' not found")
        update["icp_address"] = str(facility_doc.get("name") or facility_doc.get("address") or "")
        update["latitude"] = facility_doc.get("latitude")
        update["longitude"] = facility_doc.get("longitude")
    elif "icp_facility_id" in data and not data["icp_facility_id"]:
        update["latitude"] = None
        update["longitude"] = None
    if "latitude" in data and "icp_facility_id" not in data:
        update["latitude"] = data["latitude"]
    if "longitude" in data and "icp_facility_id" not in data:
        update["longitude"] = data["longitude"]
    if not update:
        raise HTTPException(400, "No valid fields provided")
    existing = repo.find_one({"incident_id": incident_id})
    if not existing:
        raise HTTPException(404, f"Incident '{incident_id}' not found")
    repo.update_one(existing["_id"], update)
    sys_update: dict[str, Any] = {}
    if "name" in data:
        sys_update["name"] = data["name"]
    if "number" in data:
        sys_update["number"] = data["number"]
    if "type" in data:
        sys_update["type"] = data["type"]
    if "description" in data:
        sys_update["description"] = data["description"]
    if "status" in data:
        sys_update["status"] = (data["status"] or "").lower()
    if "is_training" in data:
        sys_update["is_training"] = data["is_training"]
    if "icp_location" in data:
        sys_update["icp_location"] = update.get("icp_address", data["icp_location"])
    if "icp_facility_id" in data:
        sys_update["icp_facility_id"] = data["icp_facility_id"]
    if sys_update:
        sys_repo = _system_incidents_repo()
        sys_doc = sys_repo.find_by_id(incident_id)
        if sys_doc:
            sys_repo.update_one(incident_id, sys_update)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Header (status bar summary)
# ---------------------------------------------------------------------------

@router.get("/{incident_id}/header")
def get_header(incident_id: str) -> dict[str, Any]:
    repo = _profile_repo(incident_id)
    doc = repo.find_one({"incident_id": incident_id})
    if not doc:
        raise HTTPException(404, f"Incident '{incident_id}' not found")
    status = doc.get("status") or ""
    return {
        "incident_name": doc.get("name", ""),
        "incident_number": doc.get("incident_number", incident_id),
        "status": status[:1].upper() + status[1:] if status else "",
        "icp_location": doc.get("icp_address") or doc.get("icp_location") or "",
        "start_time": doc.get("start_time") or doc.get("created_at") or "",
    }


# ---------------------------------------------------------------------------
# Operational periods
# ---------------------------------------------------------------------------

@router.get("/{incident_id}/op-periods")
def get_op_periods(incident_id: str) -> list[int]:
    repo = _op_periods_repo(incident_id)
    docs = repo.find_many({"incident_id": incident_id, "deleted": {"$ne": True}})
    numbers: list[int] = []
    for doc in docs:
        raw = doc.get("op_number")
        if raw is None:
            continue
        try:
            numbers.append(int(str(raw).strip()))
        except (ValueError, TypeError):
            pass
    return sorted(set(numbers)) or [1]


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

@router.get("/{incident_id}/teams")
def list_teams(incident_id: str, op_no: int = 1) -> list[dict[str, Any]]:
    repo = _teams_repo(incident_id)
    # Team docs live in the per-incident database (get_incident_db) and are
    # never stamped with an "incident_id" field of their own, unlike e.g.
    # operational_periods docs - so this must not filter on that field.
    docs = repo.find_many({"deleted": {"$ne": True}})
    result = []
    for doc in docs:
        last_ts = _parse_dt(doc.get("last_checkin_at"))
        result.append({
            "team_id": doc.get("int_id", str(doc["_id"])),
            "team_name": doc.get("name", ""),
            "status": doc.get("status", "Unknown"),
            "last_checkin_ts": last_ts.isoformat() if last_ts else None,
            "needs_assistance": bool(doc.get("needs_attention", False)),
            "emergency": bool(doc.get("emergency_flag", False)),
        })
    return result


# ---------------------------------------------------------------------------
# Team locations (GIS module Phase 1 — see tracking_plan.md in ICS-Mobile-App)
# ---------------------------------------------------------------------------

@router.get("/{incident_id}/team-locations")
def list_team_locations(incident_id: str) -> list[dict[str, Any]]:
    """One row per team with a current tracked position. Called once on the
    desktop map panel's open to draw the initial marker set; live updates
    ride the existing incident websocket feed (every write already lands on
    this same TEAMS doc via BaseRepository)."""
    repo = _teams_repo(incident_id)
    docs = repo.find_many({"current_location_lat": {"$ne": None}})
    return [
        {
            "team_id": doc.get("int_id"),
            "team_name": doc.get("name", ""),
            "lat": doc.get("current_location_lat"),
            "lon": doc.get("current_location_lon"),
            "updated_at": doc.get("current_location_updated_at"),
        }
        for doc in docs
    ]


# ---------------------------------------------------------------------------
# Task summary
# ---------------------------------------------------------------------------

_TASK_STATUS_MAP = {
    "draft": "draft",
    "created": "draft",
    "pending": "draft",
    "planned": "planned",
    "assigned": "planned",
    "in progress": "in_progress",
    "in_progress": "in_progress",
    "progress": "in_progress",
    "complete": "completed",
    "completed": "completed",
    "closed": "completed",
    "cancelled": "cancelled",
    "canceled": "cancelled",
}


def _norm_task_status(val: Any) -> str:
    return _TASK_STATUS_MAP.get(str(val or "").strip().lower(), "draft")


@router.get("/{incident_id}/tasks/summary")
def task_summary(incident_id: str, op_no: int = 1) -> dict[str, Any]:
    repo = _tasks_repo(incident_id)
    # Task docs live in the per-incident database and are never stamped with
    # their own "incident_id" field - see the matching note in list_teams().
    docs = repo.find_many({"deleted": {"$ne": True}})
    counts: Counter = Counter()
    due_items: list[dict[str, Any]] = []
    for doc in docs:
        counts[_norm_task_status(doc.get("status"))] += 1
        raw_due = doc.get("due_time")
        if raw_due:
            due_ts = _parse_dt(raw_due)
            if due_ts:
                assigned = doc.get("assignment") or ""
                if not assigned:
                    teams = doc.get("task_teams") or []
                    if teams:
                        assigned = teams[0].get("team_name") or teams[0].get("team_id", "")
                due_items.append({
                    "task_id": doc.get("task_number") or doc.get("task_id", ""),
                    "title": doc.get("title") or "Untitled",
                    "due_time": due_ts.isoformat(),
                    "assigned_to": assigned,
                })
    due_items.sort(key=lambda x: x["due_time"])
    return {
        "counts": {
            "Draft": counts.get("draft", 0),
            "Planned": counts.get("planned", 0),
            "In Progress": counts.get("in_progress", 0),
            "Completed": counts.get("completed", 0),
            "Cancelled": counts.get("cancelled", 0),
        },
        "due": due_items[:3],
    }


# ---------------------------------------------------------------------------
# Communications channels
# ---------------------------------------------------------------------------

@router.get("/{incident_id}/channels")
def list_channels(incident_id: str) -> list[dict[str, Any]]:
    repo = _channels_repo(incident_id)
    docs = repo.find_many(
        {
            "incident_id": incident_id,
            "include_on_205": {"$ne": False},
            "deleted": {"$ne": True},
        },
        sort=[("sort_index", 1), ("channel", 1)],
    )
    result = []
    for doc in docs:
        updated_dt = _parse_dt(doc.get("updated_at"))
        mode = (doc.get("mode") or "").strip()[:1].upper()
        result.append({
            "name": doc.get("channel") or "",
            "function": doc.get("function") or "",
            "mode": mode,
            "remarks": doc.get("remarks") or "",
            "last_updated": updated_dt.isoformat() if updated_dt else None,
        })
    return result


# ---------------------------------------------------------------------------
# Logistics resource request counts
# ---------------------------------------------------------------------------

@router.get("/{incident_id}/logistics/counts")
def logistics_counts(incident_id: str) -> dict[str, int]:
    try:
        repo = _resource_requests_repo(incident_id)
        docs = repo.find_many({"incident_id": incident_id})
    except Exception:
        docs = []
    counts: Counter = Counter()
    for doc in docs:
        status = (doc.get("status") or "").strip().title()
        counts[status] += 1
    base: dict[str, int] = {"Pending": 0, "Approved": 0, "Filled": 0, "Cancelled": 0}
    base.update(dict(counts))
    return base


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

_ALERT_STATUSES = {
    "enroute", "arrival", "returning to base", "returning",
    "at other location", "to other location", "find",
}

_ALERT_PRIORITY = {
    "CHECKIN_OVERDUE": 0,
    "EMERGENCY": 1,
    "NEEDS_ASSISTANCE": 2,
    "CHECKIN_WARNING": 3,
}


@router.get("/{incident_id}/alerts")
def compute_alerts(incident_id: str, op_no: int = 1) -> list[dict[str, Any]]:
    teams = list_teams(incident_id, op_no)
    now_dt = datetime.now()
    alerts: list[dict[str, Any]] = []
    for team in teams:
        status = (team.get("status") or "").strip().lower()
        last_ts_raw = team.get("last_checkin_ts")
        last_ts = _parse_dt(last_ts_raw)
        if team.get("emergency"):
            alerts.append(_make_alert("EMERGENCY", team, last_ts_raw))
        if team.get("needs_assistance"):
            alerts.append(_make_alert("NEEDS_ASSISTANCE", team, last_ts_raw))
        if status in _ALERT_STATUSES and last_ts:
            last_naive = last_ts.replace(tzinfo=None)
            minutes = (now_dt - last_naive).total_seconds() / 60
            if minutes >= 60:
                alerts.append(_make_alert("CHECKIN_OVERDUE", team, last_ts_raw))
            elif minutes >= 50:
                alerts.append(_make_alert("CHECKIN_WARNING", team, last_ts_raw))
    alerts.sort(key=lambda x: (_ALERT_PRIORITY.get(x["type"], 99), x.get("team_name", "")))
    return alerts


def _make_alert(alert_type: str, team: dict[str, Any], last_ts: Any) -> dict[str, Any]:
    return {
        "type": alert_type,
        "team_id": team.get("team_id"),
        "team_name": team.get("team_name"),
        "status": team.get("status"),
        "last_checkin_ts": last_ts,
    }
