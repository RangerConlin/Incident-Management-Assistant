"""Operations data repository — proxies through SARApp API (MongoDB backend).

Qt signals and ICS-214 side effects are kept client-side.
"""
from __future__ import annotations

import json as _json
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
    except Exception:
        pass


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
        from modules.ics214.schemas import EntryCreate as _EntryCreate, StreamCreate as _StreamCreate
        inc = incident_context.get_active_incident_id()
        if inc:
            disp = _task_status_label(key).title() or key.title()
            _ics214_auto_entry(
                str(inc),
                category="task", ref_id=int(task_id),
                text=f"Task status changed to {disp}",
                ics=_ics, EntryCreate=_EntryCreate, StreamCreate=_StreamCreate,
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
        return AppState.get_active_user_id() or None
    except Exception:
        return None


def _ics214_auto_entry(
    inc: str,
    *,
    category: str,
    ref_id: int,
    text: str,
    ics,
    EntryCreate,
    StreamCreate,
    actor_user_id: str | None = None,
    source: str = "auto",
) -> None:
    """Find or create an ICS-214 stream for the given category/ref_id and append an auto entry."""
    streams = ics.list_streams(inc)
    stream = None
    ref_tag = f'"ref": "{category}:{ref_id}"'
    stream_name = f"{category.title()} {ref_id}"
    for s in streams:
        sec = s.get("section") or ""
        name = s.get("name") or ""
        if ref_tag in str(sec) or name.strip() == stream_name:
            stream = s
            break
    if stream is None:
        section = _json.dumps({"category": category, "ref": f"{category}:{ref_id}", "label": stream_name})
        stream = ics.create_stream(
            StreamCreate(incident_id=inc, name=stream_name, section=section, kind=category)
        )
    stream_id = stream.get("id") if isinstance(stream, dict) else getattr(stream, "id", None)
    if not stream_id:
        raise ValueError(f"ICS-214 stream has no id after find/create (category={category}, ref={ref_id})")
    ics.add_entry(
        inc, stream_id,
        EntryCreate(text=text, source=source, actor_user_id=actor_user_id),
        autogenerated=True,
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
        from modules.ics214.schemas import EntryCreate as _EntryCreate, StreamCreate as _StreamCreate
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
            StreamCreate=_StreamCreate,
            actor_user_id=_active_user_id(),
            source=source,
        )
    except Exception as exc:
        _log.warning("ics214_log_entry(%s:%s) failed: %s", category, ref_id, exc, exc_info=True)


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
    except Exception:
        pass

    if task_id_for_214 is not None:
        try:
            _client().patch(
                f"{_base()}/tasks/{task_id_for_214}/teams/{tt_id}/status",
                json={"status_key": key},
            )
        except Exception:
            pass

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
        from modules.ics214 import services as _ics
        from modules.ics214.schemas import EntryCreate as _EntryCreate, StreamCreate as _StreamCreate
        inc = incident_context.get_active_incident_id()
        if inc:
            disp = _TEAM_STATUS_DISPLAY.get(key, str(status_key).title())
            text = f"Team status changed to {disp}"
            uid = _active_user_id()
            if team_id_for_signals is not None:
                _ics214_auto_entry(str(inc), category="team", ref_id=int(team_id_for_signals), text=text,
                                   ics=_ics, EntryCreate=_EntryCreate, StreamCreate=_StreamCreate, actor_user_id=uid)
            if task_id_for_214 is not None:
                _ics214_auto_entry(str(inc), category="task", ref_id=int(task_id_for_214), text=text,
                                   ics=_ics, EntryCreate=_EntryCreate, StreamCreate=_StreamCreate, actor_user_id=uid)
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
    except Exception:
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
        from modules.ics214 import services as _ics
        from modules.ics214.schemas import EntryCreate as _EntryCreate, StreamCreate as _StreamCreate
        inc = incident_context.get_active_incident_id()
        if inc:
            disp = _TEAM_STATUS_DISPLAY.get(key, str(status_key).title())
            text = f"Team status changed to {disp}"
            uid = _active_user_id()
            _ics214_auto_entry(str(inc), category="team", ref_id=int(team_id), text=text,
                               ics=_ics, EntryCreate=_EntryCreate, StreamCreate=_StreamCreate, actor_user_id=uid)
            if current_task_id is not None:
                _ics214_auto_entry(str(inc), category="task", ref_id=int(current_task_id), text=text,
                                   ics=_ics, EntryCreate=_EntryCreate, StreamCreate=_StreamCreate, actor_user_id=uid)
    except Exception as exc:
        _log.warning("ICS-214 auto-log failed for team status: %s", exc, exc_info=True)


def list_tasks_for_assignment() -> List[Dict[str, Any]]:
    try:
        return _client().get(f"{_base()}/tasks-for-assignment")
    except Exception:
        return []


def set_team_assignment_status_for_task(task_id: int, tt_id: int, status_key: str) -> None:
    """Direct form: call when task_id is known (avoids scan)."""
    key = str(status_key).strip().lower()
    try:
        _client().patch(f"{_base()}/tasks/{task_id}/teams/{tt_id}/status", json={"status_key": key})
    except Exception:
        pass
