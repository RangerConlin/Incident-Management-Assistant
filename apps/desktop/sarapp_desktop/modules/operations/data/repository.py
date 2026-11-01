"""Operations data repository — proxies through SARApp API (MongoDB backend).

Qt signals and ICS-214 side effects are kept client-side.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from utils import incident_context

_log = logging.getLogger(__name__)


def _iid() -> str:
    v = incident_context.get_active_incident_id()
    if not v:
        raise RuntimeError("No active incident")
    return str(v)


def _base() -> str:
    return f"/api/incidents/{_iid()}/operations"


def _client():
    from utils.api_client import api_client
    return api_client


def _priority_label(value: Any) -> str:
    try:
        i = int(value)
    except Exception:
        return str(value) if value is not None else ""
    return {1: "Low", 2: "Medium", 3: "High", 4: "Critical"}.get(i, str(i))


def _task_status_label(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip().lower()
    return {
        "completed": "complete", "complete": "complete", "draft": "created", "created": "created",
        "planned": "planned", "assigned": "assigned", "in progress": "in progress", "cancelled": "cancelled",
    }.get(s, s)


def _iso_timestamp(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.isoformat(timespec="seconds")


# Expose as module-level so other modules can call _ensure_* guards safely
def _ensure_teams_status_columns(*args, **kwargs) -> None:
    pass


def _ensure_teams_name_column(*args, **kwargs) -> None:
    pass


def _ensure_teams_current_task_column(*args, **kwargs) -> None:
    pass


def _ensure_teams_location_column(*args, **kwargs) -> None:
    pass


def _ensure_teams_attention_column(*args, **kwargs) -> None:
    pass


def _ensure_team_alert_columns(*args, **kwargs) -> None:
    pass


def fetch_task_rows() -> List[Dict[str, Any]]:
    try:
        return _client().get(f"{_base()}/task-rows")
    except Exception:
        return []


def fetch_team_assignment_rows() -> List[Dict[str, Any]]:
    try:
        return _client().get(f"{_base()}/team-assignment-rows")
    except Exception:
        return []


def touch_team_checkin(
    team_id: int,
    *,
    checkin_time: datetime | None = None,
    reference_time: datetime | None = None,
) -> None:
    check_iso = _iso_timestamp(checkin_time or datetime.now(timezone.utc))
    ref_iso = _iso_timestamp(reference_time or checkin_time or datetime.now(timezone.utc))
    try:
        _client().patch(f"{_base()}/teams/{team_id}/checkin", json={"checkin_time": check_iso, "reference_time": ref_iso})
    except Exception as exc:
        _log.warning("touch_team_checkin API call failed for team_id=%s: %s", team_id, exc)


def set_task_status(task_id: int, status_key: str) -> None:
    key = str(status_key).strip().lower()
    try:
        _client().patch(f"{_base()}/tasks/{task_id}/status", json={"status_key": key})
    except Exception as exc:
        _log.warning("set_task_status API call failed: %s", exc)
        return

    try:
        from utils.app_signals import app_signals
        app_signals.taskHeaderChanged.emit(int(task_id), {"status": True})
    except Exception:
        pass

    try:
        from modules.ics214 import services as _ics
        from modules.ics214.schemas import EntryCreate as _EntryCreate
        inc = incident_context.get_active_incident_id()
        if inc:
            disp = _task_status_label(key).title() or key.title()
            _ics214_auto_entry(
                str(inc),
                category="task", ref_id=int(task_id),
                text=f"Task status changed to {disp}",
                ics=_ics, EntryCreate=_EntryCreate,
            )
    except Exception as exc:
        _log.warning("ICS-214 auto-log failed for task status: %s", exc, exc_info=True)


_TEAM_STATUS_DISPLAY: dict[str, str] = {
    "available":  "Available",
    "assigned":   "Assigned",
    "briefed":    "Briefed",
    "enroute":    "En Route",
    "arrival":    "On Scene",
    "on scene":   "On Scene",
    "find":       "Discovery",
    "discovery":  "Discovery",
    "complete":   "Complete",
    "returning":  "RTB",
    "rtb":        "RTB",
    "oos":        "Out of Service",
    "break":      "On Break",
}


def _active_user_id() -> str | None:
    try:
        from utils.state import AppState
        user_id = AppState.get_active_user_id()
    except Exception:
        return None
    if user_id in (None, ""):
        return None
    return str(user_id)


def _ics214_auto_entry(
    inc: str,
    *,
    category: str,
    ref_id: int,
    text: str,
    ics,
    EntryCreate,
    actor_user_id: str | None = None,
    source: str = "auto",
) -> None:
    """Create one canonical ICS-214 entry with the requested association."""
    normalized_actor_user_id = None if actor_user_id in (None, "") else str(actor_user_id)
    associations = {
        "person": "person_ids", "team": "team_ids", "task": "task_ids",
        "org_unit": "org_unit_ids", "facility": "facility_ids",
        "resource": "resource_ids", "external_agency": "external_agency_ids",
    }
    field = associations.get(category)
    if field is None:
        raise ValueError(f"Unsupported ICS-214 association category: {category}")
    payload = {
        "text": text, "source": source, "created_by": normalized_actor_user_id,
        field: [int(ref_id)], "expand_team_members": category == "team",
    }
    ics.create_entry(
        inc,
        EntryCreate(**payload),
    )


def ics214_log_entry(
    category: str,
    ref_id: int,
    text: str,
    source: str = "internal",
) -> None:
    """Public helper: append a log entry to any ICS-214 stream.

    Use source='internal' for composition changes (personnel/asset/task assignment).
    Use source='auto' for operational status changes.
    """
    try:
        from modules.ics214 import services as _ics
        from modules.ics214.schemas import EntryCreate as _EntryCreate
        inc = incident_context.get_active_incident_id()
        if not inc:
            return
        _ics214_auto_entry(
            str(inc),
            category=category,
            ref_id=ref_id,
            text=text,
            ics=_ics,
            EntryCreate=_EntryCreate,
            actor_user_id=_active_user_id(),
            source=source,
        )
    except Exception as exc:
        _log.warning("ics214_log_entry(%s:%s) failed: %s", category, ref_id, exc, exc_info=True)


def ics214_log_event(
    text: str,
    *,
    person_ids: list[int] | None = None,
    team_ids: list[int] | None = None,
    task_ids: list[int] | None = None,
    org_unit_ids: list[int] | None = None,
    facility_ids: list[int] | None = None,
    resource_ids: list[int] | None = None,
    external_agency_ids: list[int] | None = None,
    incident_wide: bool = False,
    expand_team_members: bool = False,
    source: str = "auto",
) -> None:
    """Write one event that can belong to several logical 214 logs."""
    try:
        from modules.ics214 import services
        from modules.ics214.schemas import EntryCreate
        inc = incident_context.get_active_incident_id()
        if not inc:
            return
        services.create_entry(str(inc), EntryCreate(
            text=text,
            source=source,
            created_by=_active_user_id(),
            person_ids=person_ids or [],
            team_ids=team_ids or [],
            task_ids=task_ids or [],
            org_unit_ids=org_unit_ids or [],
            facility_ids=facility_ids or [],
            resource_ids=resource_ids or [],
            external_agency_ids=external_agency_ids or [],
            incident_wide=incident_wide,
            expand_team_members=expand_team_members,
        ))
    except Exception as exc:
        _log.warning("ICS-214 event write failed: %s", exc, exc_info=True)


TS_STATUS_COLS = {
    "assigned": "time_assigned", "briefed": "time_briefed",
    "enroute": "time_enroute", "arrival": "time_arrived", "on scene": "time_arrived",
    "find": "time_discovery", "discovery": "time_discovery",
    "complete": "time_complete", "returning": "time_cleared", "rtb": "time_cleared",
}


def set_team_assignment_status(tt_id: int, status_key: str) -> None:
    """Stamp task_team timestamp via API, then fire ICS-214 entries and Qt signals."""
    key = str(status_key).strip().lower()
    # Determine which task and team from the API by searching tasks
    # We need task_id to stamp the team in the task_teams array
    task_id_for_214 = None
    team_id_for_signals = None
    try:
        tasks = _client().get(f"{_base()}/tasks")
        for task in tasks:
            for tt in task.get("task_teams") or []:
                if tt.get("id") == tt_id:
                    task_id_for_214 = int(task["int_id"])
                    team_id_for_signals = tt.get("team_id")
                    break
            if task_id_for_214 is not None:
                break
    except Exception as exc:
        _log.warning("set_team_assignment_status: task lookup for tt_id=%s failed: %s", tt_id, exc)

    if task_id_for_214 is not None:
        try:
            _client().patch(
                f"{_base()}/tasks/{task_id_for_214}/teams/{tt_id}/status",
                json={"status_key": key},
            )
        except Exception as exc:
            _log.warning("set_team_assignment_status API call failed for tt_id=%s: %s", tt_id, exc)
    else:
        _log.warning(
            "set_team_assignment_status: could not resolve task for tt_id=%s; status PATCH skipped",
            tt_id,
        )

    # Qt signals
    try:
        if team_id_for_signals is not None:
            from utils.app_signals import app_signals
            app_signals.teamStatusChanged.emit(int(team_id_for_signals))
    except Exception:
        pass
    try:
        if task_id_for_214 is not None:
            from utils.app_signals import app_signals as _sig2
            _sig2.taskHeaderChanged.emit(int(task_id_for_214), {'assigned_teams': True})
    except Exception:
        pass

    # ICS-214 entries
    try:
        inc = incident_context.get_active_incident_id()
        if inc:
            disp = _TEAM_STATUS_DISPLAY.get(key, str(status_key).title())
            text = f"Team status changed to {disp}"
            ics214_log_event(
                text,
                team_ids=[int(team_id_for_signals)] if team_id_for_signals is not None else [],
                task_ids=[int(task_id_for_214)] if task_id_for_214 is not None else [],
                expand_team_members=team_id_for_signals is not None,
            )
    except Exception as exc:
        _log.warning("ICS-214 auto-log failed for team assignment status: %s", exc, exc_info=True)


def set_team_status(team_id: int, status_key: str) -> None:
    """Update team status via API, then fire ICS-214 entries and Qt signals."""
    key = str(status_key).strip().lower()
    try:
        from utils.state import AppState
        changed_by = str(AppState.get_active_user_id() or "")
    except Exception:
        changed_by = ""
    try:
        result = _client().patch(f"{_base()}/teams/{team_id}/status", json={"status_key": key, "changed_by": changed_by})
        current_task_id = result.get("current_task_id")
    except Exception as exc:
        _log.warning("set_team_status API call failed for team_id=%s: %s", team_id, exc)
        current_task_id = None

    # Qt signals
    try:
        from utils.app_signals import app_signals
        app_signals.teamStatusChanged.emit(int(team_id))
    except Exception:
        pass
    try:
        if current_task_id is not None:
            from utils.app_signals import app_signals as _sig2
            _sig2.taskHeaderChanged.emit(int(current_task_id), {'assigned_teams': True})
    except Exception:
        pass

    # ICS-214 entries
    try:
        inc = incident_context.get_active_incident_id()
        if inc:
            disp = _TEAM_STATUS_DISPLAY.get(key, str(status_key).title())
            text = f"Team status changed to {disp}"
            ics214_log_event(
                text,
                team_ids=[int(team_id)],
                task_ids=[int(current_task_id)] if current_task_id is not None else [],
                expand_team_members=True,
            )
    except Exception as exc:
        _log.warning("ICS-214 auto-log failed for team status: %s", exc, exc_info=True)


def _cached_tasks() -> List[Dict[str, Any]] | None:
    """Return every cached task document for the active incident, if loaded."""
    try:
        from utils.incident_cache import incident_cache
        if incident_cache.incident_id != _iid():
            return None
        return incident_cache.get_all("tasks")
    except Exception:
        return None


def list_tasks_for_assignment() -> List[Dict[str, Any]]:
    docs = _cached_tasks()
    if docs is None:
        try:
            return _client().get(f"{_base()}/tasks-for-assignment")
        except Exception:
            return []
    try:
        docs = sorted(docs, key=lambda d: int(d.get("int_id") or 0))
    except Exception:
        pass
    rows: List[Dict[str, Any]] = []
    for doc in docs:
        rows.append({
            "id": doc.get("int_id"),
            "task_id": doc.get("task_id"),
            "title": doc.get("title"),
            "status": _task_status_label(doc.get("status")),
            "priority": _priority_label(doc.get("priority")),
            "location": doc.get("location") or "",
        })
    return rows


def set_team_assignment_status_for_task(task_id: int, tt_id: int, status_key: str) -> None:
    """Direct form: call when task_id is known (avoids scan)."""
    key = str(status_key).strip().lower()
    try:
        _client().patch(f"{_base()}/tasks/{task_id}/teams/{tt_id}/status", json={"status_key": key})
    except Exception as exc:
        _log.warning("set_team_assignment_status_for_task API call failed for task_id=%s tt_id=%s: %s", task_id, tt_id, exc)
