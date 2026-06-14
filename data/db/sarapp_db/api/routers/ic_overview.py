"""FastAPI router — IC overview endpoints for the active incident."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.collection_names import IncidentCollections

router = APIRouter()


def _db(incident_id: str):
    return get_incident_db(incident_id)


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        from dateutil import parser as dp
        return dp.parse(str(value))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Incident profile
# ---------------------------------------------------------------------------

@router.get("/{incident_id}/profile")
def get_profile(incident_id: str) -> dict[str, Any]:
    doc = _db(incident_id)[IncidentCollections.INCIDENT_PROFILE].find_one({"incident_id": incident_id})
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
    is_training: Optional[bool] = None


_PROFILE_FIELD_MAP = {
    "name": "name",
    "number": "incident_number",
    "type": "incident_type",
    "description": "description",
    "start_time": "start_time",
    "end_time": "end_time",
    "icp_location": "icp_address",
    "is_training": "is_training",
}


@router.patch("/{incident_id}/profile")
def patch_profile(incident_id: str, body: PatchProfileRequest) -> dict[str, Any]:
    col = _db(incident_id)[IncidentCollections.INCIDENT_PROFILE]
    data = body.model_dump(exclude_none=True)
    update: dict[str, Any] = {}
    for api_field, mongo_field in _PROFILE_FIELD_MAP.items():
        if api_field in data:
            update[mongo_field] = data[api_field]
    if "status" in data:
        update["status"] = (data["status"] or "").lower()
    if not update:
        raise HTTPException(400, "No valid fields provided")
    result = col.update_one({"incident_id": incident_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, f"Incident '{incident_id}' not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Header (status bar summary)
# ---------------------------------------------------------------------------

@router.get("/{incident_id}/header")
def get_header(incident_id: str) -> dict[str, Any]:
    doc = _db(incident_id)[IncidentCollections.INCIDENT_PROFILE].find_one({"incident_id": incident_id})
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
    docs = list(
        _db(incident_id)[IncidentCollections.OPERATIONAL_PERIODS].find(
            {"incident_id": incident_id, "deleted": {"$ne": True}},
            {"op_number": 1},
        )
    )
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
    docs = list(
        _db(incident_id)[IncidentCollections.TEAMS].find(
            {"incident_id": incident_id, "deleted": {"$ne": True}}
        )
    )
    result = []
    for doc in docs:
        last_ts = _parse_dt(doc.get("last_checkin_at"))
        result.append({
            "team_id": doc.get("team_id", str(doc["_id"])),
            "team_name": doc.get("name", ""),
            "status": doc.get("status", "Unknown"),
            "last_checkin_ts": last_ts.isoformat() if last_ts else None,
            "needs_assistance": bool(doc.get("needs_assistance", False)),
            "emergency": bool(doc.get("emergency_flag", False)),
        })
    return result


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
    docs = list(
        _db(incident_id)[IncidentCollections.TASKS].find(
            {"incident_id": incident_id, "deleted": {"$ne": True}},
            {"status": 1, "title": 1, "due_time": 1, "assignment": 1,
             "task_number": 1, "task_id": 1, "assigned_teams": 1},
        )
    )
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
                    teams = doc.get("assigned_teams") or []
                    if teams:
                        assigned = teams[0].get("team_id", "")
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
    docs = list(
        _db(incident_id)[IncidentCollections.INCIDENT_CHANNELS]
        .find(
            {
                "incident_id": incident_id,
                "include_on_205": {"$ne": False},
                "deleted": {"$ne": True},
            }
        )
        .sort([("sort_index", 1), ("channel", 1)])
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
        docs = list(
            _db(incident_id)[IncidentCollections.RESOURCE_REQUESTS].find(
                {"incident_id": incident_id},
                {"status": 1},
            )
        )
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
