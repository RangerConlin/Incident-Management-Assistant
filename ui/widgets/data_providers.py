"""
Data providers for dashboard widgets.

Each function returns live data from the active incident database with a
graceful fallback to representative demo data when no incident is loaded or
the required tables do not yet exist.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from utils.state import AppState


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _incident_number() -> str | None:
    return AppState.get_active_incident()


def _incident_conn():
    """Return a sqlite3 connection to the active incident DB, or None."""
    try:
        from utils.db import get_incident_conn
        return get_incident_conn()
    except Exception:
        try:
            import sqlite3
            from utils import incident_storage
            number = _incident_number()
            if not number:
                return None
            resolved = incident_storage.resolve_incident_paths_by_identifier(number)
            if resolved is None:
                return None
            conn = sqlite3.connect(resolved.incident_db)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception:
            return None


def _table_exists(conn, name: str) -> bool:
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        return row is not None
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Incident context
# ---------------------------------------------------------------------------

def incident_getSummary() -> Dict[str, Any]:
    try:
        from modules.command.data_access import get_incident_header
        h = get_incident_header()
        return {
            "name": h.get("incident_name", "-"),
            "number": h.get("incident_number", "-"),
            "type": h.get("incident_type", "SAR"),
            "status": h.get("status", "-"),
            "icp_location": h.get("icp_location", "-"),
            "start_time": h.get("start_time", "-"),
            "operational_period": h.get("operational_period", 1),
        }
    except Exception:
        return {
            "name": "Operation Demo",
            "number": "25-D-9001",
            "type": "SAR",
            "status": "Active",
            "icp_location": "Mock ICP",
            "start_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "operational_period": 1,
        }


def auth_getCurrentUser() -> Dict[str, Any]:
    return {
        "name": "j.doe",
        "role": "Planning Chief",
        "login": datetime.now(timezone.utc).strftime("%H:%M UTC"),
        "check_in": datetime.now(timezone.utc).strftime("%H:%M UTC"),
    }


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

_ASSIGNED_STATUSES = {
    "enroute", "arrival", "returning", "returning to base",
    "at other location", "to other location", "find",
}
_OOS_STATUSES = {"out of service", "unavailable", "demobilized", "off duty"}


def teams_getStatusSummary() -> Dict[str, int]:
    try:
        from modules.command.data_access import list_team_checkins
        teams = list_team_checkins(1)
        counts: Dict[str, int] = {"available": 0, "assigned": 0, "out_of_service": 0}
        for t in teams:
            s = str(t.get("status", "")).lower().strip()
            if s in _OOS_STATUSES:
                counts["out_of_service"] += 1
            elif s in _ASSIGNED_STATUSES or s == "assigned":
                counts["assigned"] += 1
            else:
                counts["available"] += 1
        return counts
    except Exception:
        return {"available": 4, "assigned": 6, "out_of_service": 1}


def teams_getList() -> List[Dict[str, Any]]:
    """Return the full team list with status detail."""
    try:
        from modules.command.data_access import list_team_checkins
        return list_team_checkins(1)
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def tasks_getSummary_active() -> Dict[str, int]:
    try:
        from modules.command.data_access import list_task_summary
        summary = list_task_summary(1)
        c = summary.get("counts", {})
        return {
            "draft": c.get("Draft", 0),
            "planned": c.get("Planned", 0),
            "in_progress": c.get("In Progress", 0),
            "completed": c.get("Completed", 0),
            "cancelled": c.get("Cancelled", 0),
        }
    except Exception:
        return {"draft": 2, "planned": 3, "in_progress": 7, "completed": 12, "cancelled": 0}


def tasks_getDueSoon() -> List[Dict[str, Any]]:
    """Return up to 3 tasks due soonest."""
    try:
        from modules.command.data_access import list_task_summary
        summary = list_task_summary(1)
        return summary.get("due", [])
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Personnel
# ---------------------------------------------------------------------------

def personnel_getAvailabilitySummary() -> Dict[str, int]:
    try:
        conn = _incident_conn()
        if conn is None:
            raise RuntimeError("no conn")
        with conn:
            if not _table_exists(conn, "checkins"):
                raise RuntimeError("no checkins table")
            rows = conn.execute(
                "SELECT ci_status, COUNT(*) AS cnt FROM checkins GROUP BY ci_status"
            ).fetchall()
            counts: Dict[str, int] = {}
            for row in rows:
                counts[str(row["ci_status"]).lower()] = int(row["cnt"])
            return {
                "checked_in": counts.get("checked in", counts.get("checked_in", 0)),
                "assigned": counts.get("assigned", 0),
                "available": counts.get("available", 0),
                "checked_out": counts.get("checked out", counts.get("checked_out", 0)),
            }
    except Exception:
        return {"available": 18, "assigned": 22, "unavailable": 3, "pending": 2}


# ---------------------------------------------------------------------------
# Equipment
# ---------------------------------------------------------------------------

def equipment_getSnapshot() -> Dict[str, int]:
    try:
        conn = _incident_conn()
        if conn is None:
            raise RuntimeError("no conn")
        with conn:
            if not _table_exists(conn, "equipment"):
                raise RuntimeError("no equipment table")
            rows = conn.execute(
                "SELECT condition, COUNT(*) AS cnt FROM equipment GROUP BY condition"
            ).fetchall()
            counts: Dict[str, int] = {}
            for row in rows:
                counts[str(row["condition"]).lower()] = int(row["cnt"])
            total = sum(counts.values())
            oos = counts.get("out of service", 0) + counts.get("damaged", 0)
            return {"checked_in": total, "assigned": counts.get("assigned", 0), "out_of_service": oos}
    except Exception:
        return {"checked_in": 45, "assigned": 21, "out_of_service": 3}


# ---------------------------------------------------------------------------
# Vehicles / Aircraft
# ---------------------------------------------------------------------------

def vehicles_getStatus() -> List[Dict[str, Any]]:
    try:
        conn = _incident_conn()
        if conn is None:
            raise RuntimeError("no conn")
        with conn:
            if not _table_exists(conn, "vehicles"):
                return []
            cols = {row[1] for row in conn.execute("PRAGMA table_info(vehicles)").fetchall()}
            status_col = "status_id" if "status_id" in cols else "status"
            unit_col = "license_plate" if "license_plate" in cols else "id"
            rows = conn.execute(
                f"SELECT {unit_col} AS unit, {status_col} AS status FROM vehicles ORDER BY {unit_col}"
            ).fetchall()
            return [{"unit": str(row["unit"] or "?"), "status": str(row["status"] or "?")} for row in rows]
    except Exception:
        return [{"unit": "V-1", "status": "Available"}, {"unit": "ATV-2", "status": "Assigned"}]


def aircraft_getStatus() -> List[Dict[str, Any]]:
    try:
        from modules.logistics.aircraft.repository import AircraftRepository
        repo = AircraftRepository()
        aircraft = repo.list_aircraft()
        return [
            {"tail": a.get("tail_number", "?"), "status": a.get("status", "?")}
            for a in aircraft
        ]
    except Exception:
        return [{"tail": "N123AB", "status": "On Standby"}]


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

def ops_getRecentEvents(limit: int = 20) -> List[str]:
    # No dedicated events backend yet
    return []


# ---------------------------------------------------------------------------
# Communications
# ---------------------------------------------------------------------------

def comms_getRecentMessages(limit: int = 20) -> List[str]:
    return comms_getCommsLog(limit)


def alerts_getAll_min_info() -> List[str]:
    # Merges safety alerts and any notifications
    alerts = safety_getAlerts()
    return alerts if alerts else ["No active alerts"]


def comms_getPrimaryFrequencies() -> List[str]:
    try:
        from modules.command.data_access import list_comms_channels
        channels = list_comms_channels(1)
        result = []
        for ch in channels[:12]:
            name = ch.get("channel") or ch.get("name") or "-"
            fn = ch.get("function") or ""
            mode = ch.get("mode") or ""
            parts = [name]
            if fn:
                parts.append(fn)
            if mode:
                parts.append(f"({mode})")
            result.append(" ".join(parts))
        return result if result else ["No channels configured"]
    except Exception:
        return ["CH1 155.160 – Command", "CH5 155.340 – Ops", "SAR 121.5 – Air"]


def comms_getCommsLog(limit: int = 50) -> List[str]:
    try:
        from modules.communications.traffic_log.repository import CommsLogRepository
        from modules.communications.traffic_log.models import CommsLogQuery
        repo = CommsLogRepository()
        entries = repo.list_entries(CommsLogQuery())
        result = []
        for e in entries[-(limit):]:
            ts = (e.ts_local or e.ts_utc or "")[:16].replace("T", " ")
            label = e.resource_label or "—"
            msg = (e.message or "")[:70]
            result.append(f"[{ts}] {label}: {msg}")
        return result or ["No log entries"]
    except Exception:
        return []


def comms_getChannels() -> List[Dict[str, Any]]:
    """Return raw channel dicts for richer widget display."""
    try:
        from modules.command.data_access import list_comms_channels
        return list_comms_channels(1)
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Planning & Documentation
# ---------------------------------------------------------------------------

def planning_getObjectives() -> List[str]:
    try:
        conn = _incident_conn()
        if conn is None:
            raise RuntimeError("no conn")
        with conn:
            if not _table_exists(conn, "incident_objectives"):
                raise RuntimeError("no table")
            rows = conn.execute(
                """
                SELECT text, status, priority, display_order
                FROM incident_objectives
                WHERE COALESCE(status, '') != 'archived'
                ORDER BY display_order, id
                """
            ).fetchall()
            result = []
            for i, row in enumerate(rows, 1):
                priority = (row["priority"] or "").upper()
                text = (row["text"] or "").strip()
                status = (row["status"] or "active").lower()
                prefix = f"{i}."
                if priority:
                    prefix += f" [{priority}]"
                suffix = " ✓" if status == "completed" else ""
                result.append(f"{prefix} {text}{suffix}")
            return result if result else ["No objectives defined"]
    except Exception:
        return ["1. Ensure rescuer safety", "2. Locate subject"]


def planning_getSITREP(limit: int = 25) -> List[str]:
    return []


def planning_getUpcomingTasks() -> List[str]:
    try:
        due = tasks_getDueSoon()
        result = []
        for item in due[:5]:
            title = item.get("title", "?")
            due_time = str(item.get("due_time", ""))[:16].replace("T", " ")
            team = item.get("assigned_to") or item.get("primary_team") or ""
            line = f"{title}"
            if due_time:
                line += f" — {due_time}"
            if team:
                line += f" ({team})"
            result.append(line)
        return result if result else []
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------

_RISK_LABELS = {"EH": "EXTREME", "H": "HIGH", "M": "MEDIUM", "L": "LOW"}


def safety_getAlerts() -> List[str]:
    try:
        from modules.safety.orm import service as safety_service
        incident_id = _incident_number()
        if not incident_id:
            raise RuntimeError("no incident")
        hazards = safety_service.list_hazards(incident_id, 1)
        result = []
        for h in hazards:
            risk = _RISK_LABELS.get(h.residual_risk or "", h.residual_risk or "?")
            activity = (h.sub_activity or "").strip()
            outcome = (h.hazard_outcome or "").strip()[:60]
            result.append(f"[{risk}] {activity}: {outcome}")
        return result if result else []
    except Exception:
        return []


def safety_getHazards() -> List[Any]:
    """Return raw ORMHazard objects for richer display."""
    try:
        from modules.safety.orm import service as safety_service
        incident_id = _incident_number()
        if not incident_id:
            return []
        return safety_service.list_hazards(incident_id, 1)
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Medical
# ---------------------------------------------------------------------------

def medical_getIncidentLog(limit: int = 25) -> List[str]:
    return []


def medical_get206Summary() -> Dict[str, Any]:
    return {"hospitals": 0, "medevac": "-", "plan": "-"}


# ---------------------------------------------------------------------------
# Intel
# ---------------------------------------------------------------------------

def intel_getDashboard() -> Dict[str, Any]:
    return {"clues": 0, "interviews": 0}


def intel_getClueLog(limit: int = 25) -> List[str]:
    return []


# ---------------------------------------------------------------------------
# GIS
# ---------------------------------------------------------------------------

def gis_getSnapshot() -> Dict[str, Any]:
    return {"layers": [], "zoom": 10}


# ---------------------------------------------------------------------------
# Public Information
# ---------------------------------------------------------------------------

def pio_getPressDrafts() -> List[str]:
    return []


def pio_getMediaLog(limit: int = 25) -> List[str]:
    return []


def pio_getPendingApprovals() -> List[str]:
    return []


# ---------------------------------------------------------------------------
# Weather
# ---------------------------------------------------------------------------

def weather_getSnapshot() -> Dict[str, Any]:
    """Return current weather snapshot from the WeatherApiManager cache.

    Returns a dict with keys:
      - advisories: list of dicts (event, severity, headline)
      - metar: dict of station -> raw_text
      - has_data: bool
    """
    try:
        from modules.intel.weather.services.api_link import WeatherApiManager
        mgr = WeatherApiManager.instance()
        advisories = [
            {
                "event": a.event,
                "severity": a.severity or "Unknown",
                "headline": a.headline or a.event,
            }
            for a in mgr._advisory_cache
        ]
        metar = {
            station: reading.raw_text
            for station, reading in mgr._metar_cache.items()
        }
        return {"advisories": advisories, "metar": metar, "has_data": bool(advisories or metar)}
    except Exception:
        return {"advisories": [], "metar": {}, "has_data": False}


# ---------------------------------------------------------------------------
# Operational Period
# ---------------------------------------------------------------------------

def opperiod_getActive() -> Dict[str, Any] | None:
    """Return the currently active operational period record as a dict, or None."""
    try:
        from modules.planning.operational_periods.repository import OperationalPeriodRepository
        repo = OperationalPeriodRepository()
        record = repo.get_active_period()
        if record is None:
            # Fall back to the highest-numbered period
            periods = repo.list_periods()
            if not periods:
                return None
            record = sorted(periods, key=lambda r: r.number)[-1]
        return {
            "number": record.number,
            "name": record.name or f"Period {record.number}",
            "status": record.status,
            "start_time": record.start_time,
            "end_time": record.end_time,
            "briefing_time": record.briefing_time,
            "weather_summary": record.weather_summary or "",
            "safety_message": record.safety_message or "",
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Resource Requests (ICS-213RR)
# ---------------------------------------------------------------------------

def requests_getSummary() -> Dict[str, Any]:
    """Return request counts by status and a short list of open requests."""
    try:
        from modules.logistics.resource_requests import get_service
        svc = get_service()
        all_requests = svc.list_requests({})
        counts: Dict[str, int] = {}
        for req in all_requests:
            status = str(req.get("status", "UNKNOWN")).upper()
            counts[status] = counts.get(status, 0) + 1

        open_statuses = {"SUBMITTED", "REVIEWED", "APPROVED"}
        open_requests = [
            {
                "id": req.get("id", ""),
                "title": req.get("title", "Untitled"),
                "status": req.get("status", ""),
                "priority": req.get("priority", ""),
            }
            for req in all_requests
            if str(req.get("status", "")).upper() in open_statuses
        ]
        return {"counts": counts, "open": open_requests[:8]}
    except Exception:
        return {"counts": {}, "open": []}


# ---------------------------------------------------------------------------
# ICS-214 Activity Log (all streams)
# ---------------------------------------------------------------------------

def ics214_getRecentEntries(limit: int = 30) -> List[Dict[str, Any]]:
    """Return the most recent activity log entries across all streams."""
    try:
        from modules.ics214 import services as svc214
        incident_id = _incident_number()
        if not incident_id:
            return []
        streams = svc214.list_streams(incident_id)
        all_entries: List[Dict[str, Any]] = []
        for stream in streams:
            stream_id = stream.id if hasattr(stream, "id") else stream.get("id")
            stream_name = stream.name if hasattr(stream, "name") else stream.get("name", "?")
            if not stream_id:
                continue
            entries = svc214.list_entries(incident_id, stream_id)
            for e in entries:
                e["_stream_name"] = stream_name
            all_entries.extend(entries)
        # Sort by timestamp descending
        all_entries.sort(
            key=lambda e: e.get("timestamp_utc") or "",
            reverse=True,
        )
        return all_entries[:limit]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Subject / Missing Person Profile
# ---------------------------------------------------------------------------

def subject_getProfiles() -> List[Dict[str, Any]]:
    """Return subject records for the active incident."""
    try:
        from modules.intel import services as intel_services
        subjects = intel_services.list_subjects()
        return [
                {
                    "name": s.name,
                    "sex": s.sex or "",
                    "dob": s.dob or "",
                    "lkp_time": str(s.lkp_time) if s.lkp_time else "",
                    "lkp_place": s.lkp_place or "",
                }
                for s in subjects
            ]
    except Exception:
        return []
