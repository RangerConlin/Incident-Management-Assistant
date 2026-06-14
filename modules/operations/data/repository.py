"""Operations data repository — proxies through SARApp API (MongoDB backend).

Qt signals and ICS-214 side effects are kept client-side.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from utils import incident_context


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
    try:
        _client().patch(f"{_base()}/tasks/{task_id}/status", json={"status_key": status_key})
    except Exception:
        pass


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
        from utils import incident_context as _ic
        from modules.ics214 import services as _ics
        from modules.ics214.schemas import EntryCreate as _EntryCreate, StreamCreate as _StreamCreate
        inc = _ic.get_active_incident_id()
        if inc:
            disp = {"enroute": "En Route", "arrival": "On Scene", "on scene": "On Scene", "rtb": "RTB"}.get(key, str(status_key).title())
            text = f"Team status changed to {disp}"
            streams = _ics.list_streams(str(inc))
            if team_id_for_signals is not None:
                team_stream = None
                for s in streams:
                    sec = getattr(s, 'section', None) or ''
                    name = getattr(s, 'name', '')
                    if (f'"ref": "team:{int(team_id_for_signals)}"' in str(sec)) or (name.strip() == f"Team {int(team_id_for_signals)}"):
                        team_stream = s; break
                if team_stream is None:
                    import json as _json
                    section = _json.dumps({"category": "team", "ref": f"team:{int(team_id_for_signals)}", "label": f"Team {int(team_id_for_signals)}"})
                    team_stream = _ics.create_stream(_StreamCreate(incident_id=str(inc), name=f"Team {int(team_id_for_signals)}", section=section, kind="team"))
                _ics.add_entry(str(inc), getattr(team_stream, 'id'), _EntryCreate(text=text, source="auto"), autogenerated=True)
            if task_id_for_214 is not None:
                task_stream = None
                for s in streams:
                    sec = getattr(s, 'section', None) or ''
                    name = getattr(s, 'name', '')
                    if (f'"ref": "task:{int(task_id_for_214)}"' in str(sec)) or (name.strip() == f"Task {int(task_id_for_214)}"):
                        task_stream = s; break
                if task_stream is None:
                    import json as _json
                    section = _json.dumps({"category": "task", "ref": f"task:{int(task_id_for_214)}", "label": f"Task {int(task_id_for_214)}"})
                    task_stream = _ics.create_stream(_StreamCreate(incident_id=str(inc), name=f"Task {int(task_id_for_214)}", section=section, kind="task"))
                _ics.add_entry(str(inc), getattr(task_stream, 'id'), _EntryCreate(text=text, source="auto"), autogenerated=True)
    except Exception:
        pass


def set_team_status(team_id: int, status_key: str) -> None:
    """Update team status via API, then fire ICS-214 entries and Qt signals."""
    key = str(status_key).strip().lower()
    try:
        result = _client().patch(f"{_base()}/teams/{team_id}/status", json={"status_key": key})
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
        from utils import incident_context as _ic
        from modules.ics214 import services as _ics
        from modules.ics214.schemas import EntryCreate as _EntryCreate, StreamCreate as _StreamCreate
        inc = _ic.get_active_incident_id()
        if inc:
            disp = {"enroute": "En Route", "arrival": "On Scene", "on scene": "On Scene", "rtb": "RTB"}.get(key, str(status_key).title())
            text = f"Team status changed to {disp}"
            streams = _ics.list_streams(str(inc))
            team_stream = None
            for s in streams:
                sec = getattr(s, 'section', None) or ''
                name = getattr(s, 'name', '')
                if (f'"ref": "team:{int(team_id)}"' in str(sec)) or (name.strip() == f"Team {int(team_id)}"):
                    team_stream = s; break
            if team_stream is None:
                import json as _json
                section = _json.dumps({"category": "team", "ref": f"team:{int(team_id)}", "label": f"Team {int(team_id)}"})
                team_stream = _ics.create_stream(_StreamCreate(incident_id=str(inc), name=f"Team {int(team_id)}", section=section, kind="team"))
            _ics.add_entry(str(inc), getattr(team_stream, 'id'), _EntryCreate(text=text, source="auto"), autogenerated=True)
            if current_task_id is not None:
                task_stream = None
                for s in streams:
                    sec = getattr(s, 'section', None) or ''
                    name = getattr(s, 'name', '')
                    if (f'"ref": "task:{int(current_task_id)}"' in str(sec)) or (name.strip() == f"Task {int(current_task_id)}"):
                        task_stream = s; break
                if task_stream is None:
                    import json as _json
                    section = _json.dumps({"category": "task", "ref": f"task:{int(current_task_id)}", "label": f"Task {int(current_task_id)}"})
                    task_stream = _ics.create_stream(_StreamCreate(incident_id=str(inc), name=f"Task {int(current_task_id)}", section=section, kind="task"))
                _ics.add_entry(str(inc), getattr(task_stream, 'id'), _EntryCreate(text=text, source="auto"), autogenerated=True)
    except Exception:
        pass


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
