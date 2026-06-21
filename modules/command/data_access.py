"""Data access helpers backing the IC overview widget."""
from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Optional

from utils.state import AppState
from utils import timefmt

_LOGGER = logging.getLogger(__name__)

_CURRENT_OP = 1
_ALERT_STATUSES = {
    "enroute",
    "arrival",
    "returning to base",
    "returning",
    "at other location",
    "to other location",
    "find",
}

_ALERT_PRIORITY = {
    "CHECKIN_OVERDUE": 0,
    "EMERGENCY": 1,
    "NEEDS_ASSISTANCE": 2,
    "CHECKIN_WARNING": 3,
}

_DEMO_HEADER = {
    "incident_name": "Operation Demo",
    "incident_number": "25-D-9001",
    "operational_period": 1,
    "status": "Active",
    "icp_location": "Mock ICP",
    "start_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
}

_DEMO_TEAMS: list[dict[str, Any]] = [
    {
        "team_id": 1,
        "team_name": "GT-Alpha",
        "status": "Enroute",
        "last_checkin_ts": datetime.now() - timedelta(minutes=35),
        "needs_assistance": False,
        "emergency": False,
    },
    {
        "team_id": 2,
        "team_name": "GT-Bravo",
        "status": "Arrival",
        "last_checkin_ts": datetime.now() - timedelta(minutes=58),
        "needs_assistance": True,
        "emergency": False,
    },
    {
        "team_id": 3,
        "team_name": "UDF-Charlie",
        "status": "Returning to Base",
        "last_checkin_ts": datetime.now() - timedelta(minutes=72),
        "needs_assistance": False,
        "emergency": True,
    },
    {
        "team_id": 4,
        "team_name": "Air-1",
        "status": "Available",
        "last_checkin_ts": datetime.now() - timedelta(minutes=15),
        "needs_assistance": False,
        "emergency": False,
    },
]

_DEMO_TASKS = [
    {
        "task_id": "T-101",
        "title": "Hasty Search Trailhead",
        "status": "In Progress",
        "due_time": (datetime.now() + timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%S"),
        "assigned_to": "GT-Alpha",
    },
    {
        "task_id": "T-102",
        "title": "Grid Search Sector 5",
        "status": "Planned",
        "due_time": (datetime.now() + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S"),
        "assigned_to": "GT-Bravo",
    },
    {
        "task_id": "T-103",
        "title": "Medical Evacuation Staging",
        "status": "Completed",
        "due_time": (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S"),
        "assigned_to": "Med-1",
    },
]

_DEMO_COMMS = [
    {
        "name": "Command 1",
        "function": "Command Net",
        "mode": "A",
        "remarks": "Primary",
        "last_updated": datetime.now() - timedelta(minutes=5),
    },
    {
        "name": "Air-Ground",
        "function": "Air Ops",
        "mode": "A",
        "remarks": "Contact Air-1 prior to ingress",
        "last_updated": datetime.now() - timedelta(minutes=20),
    },
    {
        "name": "Tactical 3",
        "function": "Ground Teams",
        "mode": "D",
        "remarks": "",
        "last_updated": datetime.now() - timedelta(minutes=120),
    },
]

_DEMO_LOGISTICS_COUNTS = {
    "Submitted": 2,
    "In Progress": 1,
    "Approved": 1,
    "Ordered": 0,
    "Fulfilled": 1,
    "Complete": 3,
    "Cancelled": 0,
    "Denied": 0,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _active_incident_id() -> Optional[str]:
    try:
        number = AppState.get_active_incident()
        return str(number) if number else None
    except Exception:
        return None


def _parse_datetime(value: Any) -> Optional[datetime]:
    return timefmt.to_datetime(value)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_incident_header() -> dict[str, Any]:
    incident_id = _active_incident_id()
    if incident_id:
        try:
            from utils.api_client import api_client
            result = api_client.get(f"/api/incidents/{incident_id}/header")
            result["operational_period"] = _CURRENT_OP
            return result
        except Exception:
            _LOGGER.exception("Failed to load incident header via API; using demo content")
    header = dict(_DEMO_HEADER)
    header["operational_period"] = _CURRENT_OP
    return header


def get_operational_periods() -> list[int]:
    incident_id = _active_incident_id()
    if incident_id:
        try:
            from utils.api_client import api_client
            periods: list[int] = api_client.get(f"/api/incidents/{incident_id}/op-periods")
            if periods:
                global _CURRENT_OP
                if _CURRENT_OP not in periods:
                    _CURRENT_OP = periods[0]
                return periods
        except Exception:
            _LOGGER.exception("Failed to load op periods via API")
    return [1]


def set_operational_period(op_no: int) -> None:
    global _CURRENT_OP
    if op_no <= 0:
        op_no = 1
    _CURRENT_OP = op_no
    try:
        AppState.set_active_op_period(op_no)
    except Exception:
        pass


def list_team_checkins(op_no: int) -> list[dict[str, Any]]:
    incident_id = _active_incident_id()
    if incident_id:
        try:
            from utils.api_client import api_client
            teams: list[dict[str, Any]] = api_client.get(
                f"/api/incidents/{incident_id}/teams",
                params={"op_no": op_no},
            )
            for t in teams:
                raw = t.get("last_checkin_ts")
                if raw:
                    t["last_checkin_ts"] = _parse_datetime(raw)
            return teams
        except Exception:
            _LOGGER.exception("Failed to load team check-ins via API")
    return [dict(item) for item in _DEMO_TEAMS]


def list_task_summary(op_no: int) -> dict[str, Any]:
    incident_id = _active_incident_id()
    if incident_id:
        try:
            from utils.api_client import api_client
            result: dict[str, Any] = api_client.get(
                f"/api/incidents/{incident_id}/tasks/summary",
                params={"op_no": op_no},
            )
            for item in result.get("due", []):
                raw = item.get("due_time")
                if raw:
                    item["due_time"] = _parse_datetime(raw)
            return result
        except Exception:
            _LOGGER.exception("Failed to load task summary via API")
    return _demo_task_summary()


def list_comms_channels(op_no: int) -> list[dict[str, Any]]:
    incident_id = _active_incident_id()
    if incident_id:
        try:
            from utils.api_client import api_client
            channels: list[dict[str, Any]] = api_client.get(
                f"/api/incidents/{incident_id}/channels"
            )
            for ch in channels:
                raw = ch.get("last_updated")
                if raw:
                    ch["last_updated"] = _parse_datetime(raw)
            return channels
        except Exception:
            _LOGGER.exception("Failed to load communications channels via API")
    return [dict(item) for item in _DEMO_COMMS]


def list_logistics_requests(op_no: int) -> dict[str, int]:
    incident_id = _active_incident_id()
    if incident_id:
        try:
            from utils.api_client import api_client
            return api_client.get(f"/api/incidents/{incident_id}/logistics/counts")
        except Exception:
            _LOGGER.exception("Failed to load logistics requests via API")
    return dict(_DEMO_LOGISTICS_COUNTS)


def compute_alerts(op_no: int, now: Optional[datetime] = None) -> list[dict[str, Any]]:
    incident_id = _active_incident_id()
    if incident_id:
        try:
            from utils.api_client import api_client
            alerts: list[dict[str, Any]] = api_client.get(
                f"/api/incidents/{incident_id}/alerts",
                params={"op_no": op_no},
            )
            for a in alerts:
                raw = a.get("last_checkin_ts")
                if raw:
                    a["last_checkin_ts"] = _parse_datetime(raw)
            return alerts
        except Exception:
            _LOGGER.exception("Failed to compute alerts via API; falling back to local computation")

    # Local fallback: reuse already-API-backed list_team_checkins
    now_dt = now or datetime.now()
    teams = list_team_checkins(op_no)
    alerts: list[dict[str, Any]] = []
    for team in teams:
        status = (team.get("status") or "").strip().lower()
        last_ts = team.get("last_checkin_ts")
        if team.get("emergency"):
            alerts.append(_make_alert("EMERGENCY", team, last_ts))
        if team.get("needs_assistance"):
            alerts.append(_make_alert("NEEDS_ASSISTANCE", team, last_ts))
        if status in _ALERT_STATUSES and last_ts:
            minutes = timefmt.minutes_since(last_ts, now=now_dt)
            if minutes is not None:
                if minutes >= 60:
                    alerts.append(_make_alert("CHECKIN_OVERDUE", team, last_ts))
                elif minutes >= 50:
                    alerts.append(_make_alert("CHECKIN_WARNING", team, last_ts))
    alerts.sort(key=lambda item: (_ALERT_PRIORITY.get(item["type"], 99), item.get("team_name", "")))
    return alerts


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize_task_status(value: Any) -> str:
    if value is None:
        return "draft"
    text = str(value).strip().lower()
    mapping = {
        "draft": "draft",
        "created": "draft",
        "planned": "planned",
        "assigned": "planned",
        "in progress": "in_progress",
        "progress": "in_progress",
        "complete": "completed",
        "completed": "completed",
        "closed": "completed",
        "cancelled": "cancelled",
        "canceled": "cancelled",
    }
    return mapping.get(text, text or "draft")


def _demo_task_summary() -> dict[str, Any]:
    counts: Counter = Counter()
    due_items: list[dict[str, Any]] = []
    for task in _DEMO_TASKS:
        counts[_normalize_task_status(task.get("status"))] += 1
        due = _parse_datetime(task.get("due_time"))
        if due:
            due_items.append(
                {
                    "task_id": task["task_id"],
                    "title": task["title"],
                    "due_time": due,
                    "assigned_to": task.get("assigned_to", ""),
                }
            )
    due_items.sort(key=lambda item: item["due_time"])
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


def _make_alert(alert_type: str, team: dict[str, Any], last_ts: Any) -> dict[str, Any]:
    return {
        "type": alert_type,
        "team_id": team.get("team_id"),
        "team_name": team.get("team_name"),
        "status": team.get("status"),
        "last_checkin_ts": last_ts,
    }


__all__ = [
    "get_incident_header",
    "get_operational_periods",
    "set_operational_period",
    "list_team_checkins",
    "list_task_summary",
    "list_comms_channels",
    "list_logistics_requests",
    "compute_alerts",
]
