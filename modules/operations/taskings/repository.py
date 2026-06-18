"""Operations taskings repository — proxies through SARApp API (MongoDB backend)."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from utils import incident_context
from utils.audit import write_audit
from .models import Task, TaskTeam, TaskDetail

logger = logging.getLogger(__name__)

PRIORITY_MAP = {1: "Low", 2: "Medium", 3: "High", 4: "Critical"}
PRIORITY_INT_MAP = {"low": 1, "medium": 2, "high": 3, "critical": 4}


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


def _priority_to_db(value: Any) -> int | None:
    if value is None:
        return None
    s = str(value).strip().lower()
    mapping = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    if s in mapping:
        return mapping[s]
    try:
        return int(value)
    except Exception:
        return None


def _status_to_db(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip().lower()
    inv = {
        "created": "Draft", "draft": "Draft", "planned": "Planned", "assigned": "Assigned",
        "in progress": "In Progress", "complete": "Completed", "completed": "Completed",
        "cancelled": "Cancelled",
    }
    return inv.get(s, str(value))


def _task_status_to_key(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip().lower()
    return {
        "completed": "complete", "complete": "complete", "draft": "created", "created": "created",
        "planned": "planned", "assigned": "assigned", "in progress": "in progress", "cancelled": "cancelled",
    }.get(s, s)


def _team_status_from_tt(tt: dict) -> str:
    if tt.get("time_cleared"):
        return "RTB"
    if tt.get("time_complete"):
        return "Complete"
    if tt.get("time_arrived"):
        return "On Scene"
    if tt.get("time_enroute"):
        return "En Route"
    if tt.get("time_briefed"):
        return "Briefed"
    return "Assigned"


def get_task(task_id: int) -> Task:
    doc = _client().get(f"{_base()}/tasks/{task_id}")
    priority = doc.get("priority", "")
    if isinstance(priority, int):
        priority = PRIORITY_MAP.get(priority, str(priority))
    return Task(
        id=int(doc["int_id"]),
        task_id=doc.get("task_id") or f"T-{doc['int_id']}",
        title=doc.get("title") or "",
        description="",
        category=doc.get("category") or "<New Task>",
        task_type=doc.get("task_type"),
        priority=priority,
        status=_task_status_to_key(doc.get("status")).title() if doc.get("status") else "",
        location=doc.get("location") or "",
        created_by=doc.get("created_by") or "",
        created_at=doc.get("created_at") or "",
        assigned_to=None,
        due_time=doc.get("due_time"),
        assignment=doc.get("assignment") or "",
        team_leader=doc.get("team_leader") or "",
        team_phone=doc.get("team_phone") or "",
    )


def update_task_header(task_id: int, patch: Dict[str, Any]) -> None:
    patch = dict(patch or {})
    translated: Dict[str, Any] = {}
    if "task_id" in patch:
        translated["task_id"] = str(patch["task_id"]) or None
    if "title" in patch:
        translated["title"] = str(patch["title"]) or None
    if "category" in patch:
        translated["category"] = str(patch["category"]) or None
    if "task_type" in patch:
        translated["task_type"] = str(patch["task_type"]) or None
    if "priority" in patch:
        p = _priority_to_db(patch["priority"])
        translated["priority"] = PRIORITY_MAP.get(p, str(patch["priority"])) if p else str(patch["priority"])
    if "status" in patch:
        translated["status"] = _status_to_db(patch["status"])
    if "location" in patch:
        translated["location"] = str(patch["location"]) or None
    if "assignment" in patch:
        translated["assignment"] = str(patch["assignment"]) or None
    if "team_leader" in patch:
        translated["team_leader"] = str(patch["team_leader"]) or None
    if "team_phone" in patch:
        translated["team_phone"] = str(patch["team_phone"]) or None
    if not translated:
        return
    _client().patch(f"{_base()}/tasks/{task_id}", json=translated)


def list_task_teams(task_id: int) -> List[TaskTeam]:
    rows = _client().get(f"{_base()}/tasks/{task_id}/teams")
    out: List[TaskTeam] = []
    for r in rows:
        out.append(TaskTeam(
            id=int(r.get("id") or 0),
            team_id=int(r.get("team_id") or 0),
            team_name=r.get("team_name") or f"Team {r.get('team_id')}",
            team_leader=r.get("team_leader") or "",
            team_leader_phone=r.get("team_leader_phone") or "",
            status=_team_status_from_tt(r),
            sortie_number=r.get("sortie_id"),
            assigned_ts=r.get("time_assigned"),
            briefed_ts=r.get("time_briefed"),
            enroute_ts=r.get("time_enroute"),
            arrival_ts=r.get("time_arrived"),
            discovery_ts=r.get("time_discovery"),
            complete_ts=r.get("time_complete"),
            primary=bool(r.get("is_primary")),
        ))
    return out


def list_task_personnel(task_id: int) -> List[Dict[str, Any]]:
    """Personnel list deferred until personnel module migrated."""
    try:
        return _client().get(f"{_base()}/tasks/{task_id}/personnel")
    except Exception:
        return []


def list_task_vehicles(task_id: int) -> List[Dict[str, Any]]:
    """Vehicles list deferred until vehicle module migrated."""
    try:
        return _client().get(f"{_base()}/tasks/{task_id}/vehicles")
    except Exception:
        return []


def list_task_aircraft(task_id: int) -> List[Dict[str, Any]]:
    """Aircraft list deferred until aircraft module migrated."""
    try:
        return _client().get(f"{_base()}/tasks/{task_id}/aircraft")
    except Exception:
        return []


def get_task_assignment(task_id: int) -> Dict[str, Any]:
    try:
        return _client().get(f"{_base()}/tasks/{task_id}/assignment")
    except Exception:
        return {}


def save_task_assignment(task_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    return _client().put(f"{_base()}/tasks/{task_id}/assignment", json=data)


def export_assignment_forms(task_id: int, forms: List[str], team: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """PDF export stub — returns empty list until ICS-204 template is wired."""
    return []


def list_incident_channels() -> List[Dict[str, Any]]:
    try:
        return _client().get(f"{_base()}/incident-channels")
    except Exception:
        return []


def list_task_comms(task_id: int) -> List[Dict[str, Any]]:
    try:
        return _client().get(f"{_base()}/tasks/{task_id}/comms")
    except Exception:
        return []


def add_task_comm(task_id: int, incident_channel_id: Optional[int] = None, function: Optional[str] = None, remarks: Optional[str] = None) -> int:
    result = _client().post(f"{_base()}/tasks/{task_id}/comms", json={
        "incident_channel_id": incident_channel_id,
        "function": function,
        "remarks": remarks,
    })
    return int(result.get("id") or 0)


def update_task_comm(row_id: int, incident_channel_id: Optional[int] = None, function: Optional[str] = None) -> None:
    """Requires task_id; callers must use update_task_comm_for_task instead."""
    pass


def update_task_comm_for_task(task_id: int, comm_id: int, incident_channel_id: Optional[int] = None, function: Optional[str] = None) -> None:
    patch: dict = {}
    if incident_channel_id is not None:
        patch["incident_channel_id"] = incident_channel_id
    if function is not None:
        patch["function"] = function
    if patch:
        _client().patch(f"{_base()}/tasks/{task_id}/comms/{comm_id}", json=patch)


def remove_task_comm(row_id: int) -> None:
    """Requires task_id to call the route. Callers must use remove_task_comm_for_task instead."""
    pass


def remove_task_comm_for_task(task_id: int, comm_id: int) -> None:
    _client().delete(f"{_base()}/tasks/{task_id}/comms/{comm_id}")


def list_task_debriefs(task_id: int) -> List[Dict[str, Any]]:
    try:
        return _client().get(f"{_base()}/tasks/{task_id}/debriefs")
    except Exception:
        return []


def create_debrief(task_id: int, sortie_number: str, debriefer_id: str, types: List[str]) -> int:
    result = _client().post(f"{_base()}/tasks/{task_id}/debriefs", json={
        "sortie_number": sortie_number,
        "debriefer_id": debriefer_id,
        "types": list(types or []),
    })
    return int(result.get("int_id") or 0)


def update_debrief_header(debrief_id: int, patch: Dict[str, Any]) -> None:
    _client().patch(f"{_base()}/debriefs/{debrief_id}", json=patch)


def save_debrief_form(debrief_id: int, form_key: str, data: Dict[str, Any]) -> None:
    _client().put(f"{_base()}/debriefs/{debrief_id}/forms/{form_key}", json=data)


def get_debrief(debrief_id: int) -> Dict[str, Any]:
    try:
        return _client().get(f"{_base()}/debriefs/{debrief_id}")
    except Exception:
        return {}


def archive_debrief(debrief_id: int) -> None:
    _client().post(f"{_base()}/debriefs/{debrief_id}/archive", json={})


def delete_debrief(debrief_id: int) -> None:
    _client().delete(f"{_base()}/debriefs/{debrief_id}")


def list_audit_logs(
    task_id: Optional[int] = None,
    search: str = "",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    field_filter: str = "",
    limit: int = 500,
    sort_key: Optional[str] = None,
    sort_dir: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if task_id is None:
        return []
    try:
        return _client().get(f"{_base()}/tasks/{task_id}/audit", params={"page_size": limit})
    except Exception:
        return []


def _fetch_all_audit_entries(task_id: int) -> List[Dict[str, Any]]:
    """Fetch every audit entry for a task, looping through API pages."""
    page_size = 200
    page = 1
    all_rows: List[Dict[str, Any]] = []
    while True:
        try:
            batch = _client().get(
                f"{_base()}/tasks/{task_id}/audit",
                params={"page": page, "page_size": page_size},
            )
        except Exception:
            break
        if not batch:
            break
        all_rows.extend(batch)
        if len(batch) < page_size:
            break
        page += 1
    return all_rows


def _filter_audit_rows(
    rows: List[Dict[str, Any]],
    search: str = "",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    field_filter: str = "",
) -> List[Dict[str, Any]]:
    import json as _json
    search_lc = search.strip().lower()
    field_lc = field_filter.strip().lower()
    out = []
    for r in rows:
        raw_ts = str(r.get("ts_utc") or r.get("timestamp") or "")
        if date_from and raw_ts and raw_ts[:10] < date_from:
            continue
        if date_to and raw_ts and raw_ts[:10] > date_to:
            continue
        field = str(r.get("field_changed") or r.get("action") or "")
        old = str(r.get("old_value") or "")
        new = str(r.get("new_value") or "")
        by = str(r.get("changed_by_display") or r.get("user_id") or "")
        if not field and r.get("detail"):
            try:
                d = _json.loads(r.get("detail") or "{}")
                field = field or str(d.get("field") or d.get("field_changed") or "")
                old = old or str(d.get("old") or d.get("old_value") or "")
                new = new or str(d.get("new") or d.get("new_value") or "")
            except Exception:
                pass
        if field_lc and field_lc not in field.lower():
            continue
        if search_lc and not any(search_lc in v.lower() for v in (raw_ts, field, old, new, by)):
            continue
        out.append({**r, "_field": field, "_old": old, "_new": new, "_by": by, "_ts": raw_ts})
    return out


def export_audit_csv(
    task_id: Optional[int] = None,
    output_path: Optional[str] = None,
    search: str = "",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    field_filter: str = "",
    **kwargs,
) -> Optional[str]:
    """Fetch all audit entries for the task and write to a CSV file."""
    import csv
    from datetime import datetime, timezone as _tz

    if task_id is None or output_path is None:
        return None

    rows = _filter_audit_rows(
        _fetch_all_audit_entries(int(task_id)),
        search=search,
        date_from=date_from,
        date_to=date_to,
        field_filter=field_filter,
    )

    def _fmt(ts: str) -> str:
        if not ts:
            return ""
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return ts

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Timestamp", "Field Changed", "Old Value", "New Value", "Changed By"])
        for r in rows:
            w.writerow([_fmt(r["_ts"]), r["_field"], r["_old"], r["_new"], r["_by"]])

    return output_path


def export_audit_as_214(
    task_id: int,
    output_path: str,
    search: str = "",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    field_filter: str = "",
) -> str:
    """Export the task audit log as an ICS-214 Activity Log PDF via the form engine."""
    from datetime import datetime, timezone as _tz
    from pathlib import Path

    rows = _filter_audit_rows(
        _fetch_all_audit_entries(int(task_id)),
        search=search,
        date_from=date_from,
        date_to=date_to,
        field_filter=field_filter,
    )

    def _iso(ts: str) -> str:
        if not ts:
            return ""
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(_tz.utc).isoformat(timespec="seconds")
        except Exception:
            return ts

    entries = []
    for r in rows:
        field, old, new, by = r["_field"], r["_old"], r["_new"], r["_by"]
        if old and new:
            text = f"{field}: {old} → {new}"
        elif new:
            text = f"{field}: {new}"
        else:
            text = field
        entries.append({
            "timestamp_utc": _iso(r["_ts"]),
            "text": text,
            "actor_user_id": by,
            "autogenerated": True,
        })

    from modules.forms_creator.api import export_form_unified
    result = export_form_unified(
        "ics_214",
        Path(output_path),
        values={"entries": entries},
    )
    return str(result.path)


def list_team_status_log(task_id: int) -> List[Dict[str, Any]]:
    try:
        return _client().get(f"{_base()}/tasks/{task_id}/team-status-log")
    except Exception:
        return []


def get_task_detail(task_id: int) -> TaskDetail:
    doc = _client().get(f"{_base()}/tasks/{task_id}")
    priority = doc.get("priority", "")
    if isinstance(priority, int):
        priority = PRIORITY_MAP.get(priority, str(priority))
    task = Task(
        id=int(doc["int_id"]),
        task_id=doc.get("task_id") or f"T-{doc['int_id']}",
        title=doc.get("title") or "",
        description="",
        category=doc.get("category") or "",
        task_type=doc.get("task_type"),
        priority=priority,
        status=_task_status_to_key(doc.get("status")).title() if doc.get("status") else "",
        location=doc.get("location") or "",
        created_by=doc.get("created_by") or "",
        created_at=doc.get("created_at") or "",
        assigned_to=None,
        due_time=doc.get("due_time"),
        assignment=doc.get("assignment") or "",
        team_leader=doc.get("team_leader") or "",
        team_phone=doc.get("team_phone") or "",
    )
    return TaskDetail(task=task)


def create_team(team_leader_id: Optional[int] = None) -> int:
    result = _client().post(f"{_base()}/teams", json={"team_leader": team_leader_id})
    team_int_id = int(result.get("int_id") or 0)
    # Auto-create ICS-214 stream for this team
    try:
        from modules.ics214 import services as ics214_services
        from modules.ics214.schemas import StreamCreate
        iid = _iid()
        label = f"Team {team_int_id}"
        import json as _json
        section = _json.dumps({"category": "team", "ref": f"team:{team_int_id}", "label": label})
        ics214_services.create_stream(StreamCreate(
            incident_id=str(iid), name=label, op_number=0, kind="team", section=section,
        ))
    except Exception as exc:
        logger.debug("ICS-214 stream creation for team %s: %s", team_int_id, exc)
    return team_int_id


def add_task_team(task_id: int, team_id: Optional[int] = None, sortie_id: Optional[str] = None, primary: bool = False) -> int:
    result = _client().post(f"{_base()}/tasks/{task_id}/teams", json={
        "team_id": team_id,
        "sortie_id": sortie_id,
        "primary": primary,
    })
    tt_id = int(result.get("tt_id") or 0)
    actual_team_id = int(result.get("team_id") or team_id or 0) or None
    # Set team assignment status to "assigned" (fires its own ICS-214 auto entry)
    try:
        from modules.operations.data.repository import set_team_assignment_status, ics214_log_entry
        set_team_assignment_status(tt_id, "assigned")
        if actual_team_id:
            ics214_log_entry("team", actual_team_id, f"Assigned to Task {task_id}")
        ics214_log_entry("task", int(task_id), f"Team {actual_team_id or tt_id} assigned to task")
    except Exception:
        pass
    try:
        write_audit("task.team.add", {"task_id": int(task_id), "team_id": actual_team_id, "tt_id": tt_id, "sortie_id": sortie_id, "primary": primary})
    except Exception:
        pass
    return tt_id


def set_primary_team(task_id: int, tt_id: int) -> None:
    _client().patch(f"{_base()}/tasks/{task_id}/teams/{tt_id}/primary", json={})


def update_sortie_id(tt_id: int, sortie_id: Optional[str]) -> None:
    # We need task_id — scan for the tt_id
    # Best effort: callers in task_detail_widget pass context that includes task_id
    # Stub for now — this would require a search endpoint or embedding task_id knowledge
    pass


def update_sortie_id_for_task(task_id: int, tt_id: int, sortie_id: Optional[str]) -> None:
    _client().patch(f"{_base()}/tasks/{task_id}/teams/{tt_id}/sortie", json={"sortie_id": sortie_id})
    try:
        write_audit("task.team.sortie", {"task_id": int(task_id), "tt_id": int(tt_id), "new": sortie_id})
    except Exception:
        pass


def remove_task_team(tt_id: int) -> None:
    """Scan tasks to find the owning task_id, then delegate to remove_task_team_from_task."""
    try:
        tasks = _client().get(f"{_base()}/tasks")
        for task in tasks:
            for tt in task.get("task_teams") or []:
                if tt.get("id") == tt_id:
                    remove_task_team_from_task(
                        int(task["int_id"]),
                        tt_id,
                        team_id=tt.get("team_id"),
                    )
                    return
    except Exception:
        pass


def remove_task_team_from_task(task_id: int, tt_id: int, team_id: Optional[int] = None) -> None:
    _client().delete(f"{_base()}/tasks/{task_id}/teams/{tt_id}")
    try:
        from modules.operations.data.repository import ics214_log_entry
        if team_id:
            ics214_log_entry("team", int(team_id), f"Removed from Task {task_id}")
        ics214_log_entry("task", int(task_id), f"Team {team_id or tt_id} removed from task")
    except Exception:
        pass
    try:
        write_audit("task.team.remove", {"task_id": task_id, "tt_id": tt_id, "team_id": team_id})
    except Exception:
        pass


def delete_team(team_id: int) -> None:
    _client().delete(f"{_base()}/teams/{team_id}")


def list_all_teams() -> List[Dict[str, Any]]:
    try:
        teams = _client().get(f"{_base()}/teams")
        out = []
        for t in teams:
            out.append({
                "team_id": int(t.get("int_id") or 0),
                "team_name": t.get("name") or f"Team {t.get('int_id')}",
                "team_leader": t.get("leader_name") or "",
                "team_leader_phone": t.get("leader_phone") or t.get("phone") or "",
            })
        return out
    except Exception:
        return []


def create_task(title: str = "<New Task>", task_identifier: Optional[str] = None, priority: int = 2, status: str = "Draft") -> int:
    priority_str = {1: "Low", 2: "Medium", 3: "High", 4: "Critical"}.get(priority, "Medium")
    result = _client().post(f"{_base()}/tasks", json={
        "title": title,
        "task_id": task_identifier,
        "priority": priority_str,
        "status": status,
    })
    return int(result.get("int_id") or 0)
