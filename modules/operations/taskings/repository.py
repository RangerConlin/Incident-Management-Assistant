"""Operations taskings repository — proxies through SARApp API (MongoDB backend)."""
from __future__ import annotations

import logging
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from modules.admin.resource_types.data.resource_assignment_repository import ApiResourceAssignmentRepository
from modules.forms_creator.engine import generate as generate_form_pdf
from modules.intel.weather.services.summary import build_weather_form_payload
from modules.operations.teams.data.repository import get_team
from utils import incident_context
from utils.audit import write_audit
from .models import Task, TaskTeam, TaskDetail
from models.queries import (
    fetch_team_equipment,
    fetch_team_personnel,
    fetch_team_vehicles,
)

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
        location_facility_id=doc.get("location_facility_id") or "",
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
    original = dict(patch)
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
    if "location_facility_id" in patch:
        translated["location_facility_id"] = str(patch["location_facility_id"]) or None
    if "assignment" in patch:
        translated["assignment"] = str(patch["assignment"]) or None
    if "team_leader" in patch:
        translated["team_leader"] = str(patch["team_leader"]) or None
    if "team_phone" in patch:
        translated["team_phone"] = str(patch["team_phone"]) or None
    if not translated:
        return
    translated["changed_by"] = _active_user_display()
    _client().patch(f"{_base()}/tasks/{task_id}", json=translated)
    try:
        write_audit("task.header.update", {"task_id": int(task_id), "changes": original})
    except Exception:
        pass


def _active_user_display() -> str:
    try:
        from utils.state import AppState
        uid = AppState.get_active_user_id()
        return str(uid) if uid is not None else ""
    except Exception:
        return ""


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
    """Export one or more assignment forms as PDFs."""
    form_specs = {
        "ICS 204": ("ics_204", "fema"),
        "CAPF 109": ("capf_109", "cap"),
        "SAR 104": ("sar_104", "sar"),
    }
    exports: List[Dict[str, Any]] = []
    context = _build_assignment_export_context(task_id, team)

    try:
        from utils import incident_context as _incident_context
        incident_id = _incident_context.get_active_incident_id() or "unknown"
    except Exception:
        incident_id = "unknown"

    out_dir = Path("data") / "exports" / str(incident_id) / f"task_{int(task_id)}"
    out_dir.mkdir(parents=True, exist_ok=True)

    for form_label in forms:
        spec = form_specs.get(str(form_label).strip())
        if not spec:
            continue
        form_id, form_set_id = spec
        out_path = out_dir / f"{form_id}.pdf"
        written = generate_form_pdf(
            form_id,
            out_path,
            form_set_id=form_set_id,
            extra_data=context,
        )
        exports.append(
            {
                "form": form_label,
                "form_id": form_id,
                "form_set_id": form_set_id,
                "file_path": str(written),
            }
        )
    return exports


def _safe_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    return str(value).strip()


def _task_dict(task_id: int) -> dict[str, Any]:
    try:
        return _client().get(f"{_base()}/tasks/{task_id}") or {}
    except Exception:
        return {}


def _normalize_team_dict(team: Optional[Dict[str, Any]]) -> dict[str, Any]:
    if not team:
        return {}
    if is_dataclass(team):
        return asdict(team)
    return dict(team)


def _build_pod_matrix(selected: Any) -> dict[str, str]:
    chosen = _safe_text(selected).lower()
    return {
        "high": "X" if chosen == "high" else "",
        "medium": "X" if chosen == "medium" else "",
        "low": "X" if chosen == "low" else "",
    }


def _build_assignment_export_context(task_id: int, team: Optional[Dict[str, Any]] = None) -> dict[str, Any]:
    task_doc = _task_dict(task_id)
    assignment = get_task_assignment(task_id) or {}
    team_rows = list_task_teams(task_id)
    selected_team = _normalize_team_dict(team)

    team_id = None
    for candidate in (selected_team.get("team_id"), selected_team.get("id")):
        try:
            if candidate not in (None, ""):
                team_id = int(candidate)
                break
        except Exception:
            continue

    selected_task_team = None
    if team_id is not None:
        for row in team_rows:
            try:
                row_team_id = int(getattr(row, "team_id", None) if not isinstance(row, dict) else row.get("team_id") or 0)
            except Exception:
                row_team_id = None
            if row_team_id == team_id:
                selected_task_team = row
                break
    if selected_task_team is None:
        selected_task_team = team_rows[0] if team_rows else {}

    if is_dataclass(selected_task_team):
        selected_task_team = asdict(selected_task_team)
    elif selected_task_team is None:
        selected_task_team = {}
    else:
        selected_task_team = dict(selected_task_team)

    if team_id is None:
        try:
            fallback_team_id = selected_task_team.get("team_id") or selected_task_team.get("id")
            if fallback_team_id not in (None, ""):
                team_id = int(fallback_team_id)
        except Exception:
            team_id = None

    full_team = get_team(team_id) if team_id is not None else None
    full_team_dict = asdict(full_team) if full_team else {}

    resource_type_repo = ApiResourceAssignmentRepository()
    resource_type_id = full_team_dict.get("resource_type_id") if full_team_dict else None
    resource_type_name = resource_type_repo.get_resource_type_name(resource_type_id)

    personnel_rows = fetch_team_personnel(team_id) if team_id is not None else []
    normalized_people: list[dict[str, Any]] = []
    for row in personnel_rows:
        normalized_people.append(
            {
                "id": row.get("id"),
                "member_name": _safe_text(row.get("name") or row.get("identifier") or row.get("callsign")),
                "member_agency": _safe_text(row.get("organization") or row.get("agency") or row.get("home_unit")),
                "member_medic": bool(row.get("is_medic")),
                "member_role": _safe_text(row.get("role")),
            }
        )

    leader_name = _safe_text(
        selected_task_team.get("team_leader")
        or full_team_dict.get("team_leader_name")
    )
    leader_phone = _safe_text(
        selected_task_team.get("team_leader_phone")
        or full_team_dict.get("team_leader_phone")
        or full_team_dict.get("phone")
    )

    if full_team_dict.get("team_leader_id") not in (None, ""):
        leader_id = full_team_dict.get("team_leader_id")
        for row in normalized_people:
            try:
                if int(row.get("id")) == int(leader_id):
                    if not leader_name:
                        leader_name = row["member_name"]
                    if not leader_phone:
                        leader_phone = _safe_text(row.get("phone"))
                    break
            except Exception:
                continue
    if not leader_name and normalized_people:
        leader_name = normalized_people[0]["member_name"]
    leader_agency = ""
    for row in normalized_people:
        if leader_name and row["member_name"] and row["member_name"].strip().lower() == leader_name.strip().lower():
            leader_agency = row["member_agency"]
            break
    if not leader_agency and normalized_people:
        leader_agency = normalized_people[0]["member_agency"]

    if normalized_people:
        leader_index = None
        leader_id = full_team_dict.get("team_leader_id")
        if leader_id not in (None, ""):
            for index, row in enumerate(normalized_people):
                try:
                    if int(row.get("id")) == int(leader_id):
                        leader_index = index
                        break
                except Exception:
                    continue
        if leader_index is None and leader_name:
            for index, row in enumerate(normalized_people):
                if row["member_name"] and row["member_name"].strip().lower() == leader_name.strip().lower():
                    leader_index = index
                    break
        if leader_index not in (None, 0):
            normalized_people = [normalized_people[leader_index]] + [
                row for idx, row in enumerate(normalized_people) if idx != leader_index
            ]

    team_name = _safe_text(
        selected_task_team.get("team_name")
        or full_team_dict.get("callsign")
        or full_team_dict.get("name")
    )
    if not team_name and resource_type_name:
        team_name = resource_type_name

    team_payload = {
        "team_id": team_id,
        "id": team_id,
        "name": team_name,
        "callsign": _safe_text(full_team_dict.get("callsign") or selected_task_team.get("sortie_number")),
        "resource_type": resource_type_name or _safe_text(full_team_dict.get("team_type") or selected_task_team.get("team_type")),
        "role": _safe_text(full_team_dict.get("role") or "Team Leader"),
        "status": _safe_text(selected_task_team.get("status") or full_team_dict.get("status")),
        "leader_name": leader_name,
        "leader_agency": leader_agency,
        "leader_phone": leader_phone,
        "team_leader": leader_name,
        "team_phone": leader_phone,
        "assigned_ts": _safe_text(selected_task_team.get("assigned_ts")),
        "briefed_ts": _safe_text(selected_task_team.get("briefed_ts")),
        "enroute_ts": _safe_text(selected_task_team.get("enroute_ts")),
        "arrival_ts": _safe_text(selected_task_team.get("arrival_ts")),
        "complete_ts": _safe_text(selected_task_team.get("complete_ts")),
    }

    task_payload = {
        "id": task_doc.get("int_id") or task_id,
        "task_id": _safe_text(task_doc.get("task_id") or f"T-{task_id}"),
        "title": _safe_text(task_doc.get("title")),
        "description": _safe_text(task_doc.get("description")),
        "location": _safe_text(task_doc.get("location")),
        "location_facility_id": _safe_text(task_doc.get("location_facility_id")),
        "assignment": _safe_text(task_doc.get("assignment") or assignment.get("ground", {}).get("present_search_efforts")),
        "due_time": _safe_text(task_doc.get("due_time")),
        "team_leader": leader_name,
        "team_phone": leader_phone,
        "radio_primary": _safe_text(task_doc.get("radio_primary")),
        "radio_alternate": _safe_text(task_doc.get("radio_alternate")),
        "radio_emergency": _safe_text(task_doc.get("radio_emergency")),
    }
    task_payload["radio_summary"] = "\n".join(
        part for part in [
            f"Primary: {task_payload['radio_primary']}" if task_payload["radio_primary"] else "",
            f"Alternate: {task_payload['radio_alternate']}" if task_payload["radio_alternate"] else "",
            f"Emergency: {task_payload['radio_emergency']}" if task_payload["radio_emergency"] else "",
        ] if part
    )

    ground = dict(assignment.get("ground") or {})
    expected_pod = dict(ground.get("expected_pod") or {})
    assignment_payload = {
        "ground": {
            "previous_search_efforts": _safe_text(ground.get("previous_search_efforts")),
            "present_search_efforts": _safe_text(ground.get("present_search_efforts")),
            "time_allocated": _safe_text(ground.get("time_allocated")),
            "size_of_assignment": _safe_text(ground.get("size_of_assignment")),
            "drop_off_instructions": _safe_text(ground.get("drop_off_instructions")),
            "pickup_instructions": _safe_text(ground.get("pickup_instructions")),
            "transport_instructions": _safe_text(
                ground.get("drop_off_instructions") or ground.get("pickup_instructions")
            ),
            "expected_pod": {
                "responsive": _build_pod_matrix(expected_pod.get("responsive")),
                "unresponsive": _build_pod_matrix(expected_pod.get("unresponsive")),
                "clues": _build_pod_matrix(expected_pod.get("clues")),
            },
        },
    }
    if assignment.get("air"):
        assignment_payload["air"] = dict(assignment.get("air") or {})

    team_member_rows = normalized_people[:8]
    additional_names = ", ".join(row["member_name"] for row in normalized_people[8:] if row.get("member_name"))

    attachments = []
    try:
        from modules.operations.taskings.attachments import list_attachments
        attachments = list_attachments(task_id)
    except Exception:
        attachments = []
    map_files = [row.get("filename") or "" for row in attachments if "map" in _safe_text(row.get("filename")).lower()]
    debrief_files = [
        row.get("filename") or ""
        for row in attachments
        if any(term in _safe_text(row.get("filename")).lower() for term in ("debrief", "brief"))
    ]
    equipment_issued = []
    try:
        if team_id is not None:
            equipment_issued.extend(
                _safe_text(row.get("name") or row.get("type"))
                for row in fetch_team_equipment(team_id)
                if _safe_text(row.get("name") or row.get("type"))
            )
            equipment_issued.extend(
                _safe_text(row.get("name") or row.get("callsign") or row.get("type"))
                for row in fetch_team_vehicles(team_id)
                if _safe_text(row.get("name") or row.get("callsign") or row.get("type"))
            )
    except Exception:
        equipment_issued = []

    weather_config = {}
    try:
        weather_config = _client().get(f"/api/incidents/{_iid()}/weather") or {}
    except Exception:
        weather_config = {}
    weather_payload = build_weather_form_payload(weather_config)

    return {
        "task": task_payload,
        "team": team_payload,
        "assignment": assignment_payload,
        "weather": weather_payload,
        "team_members": team_member_rows,
        "additional": {"names": additional_names},
        "subject": dict(assignment.get("subject") or {}) if isinstance(assignment.get("subject"), dict) else {},
        "radio_call": task_payload.get("radio_summary") or "",
        "previous_search_effort": assignment_payload["ground"]["previous_search_efforts"],
        "time_allocated": assignment_payload["ground"]["time_allocated"],
        "size_of_assignment": assignment_payload["ground"]["size_of_assignment"],
        "transport_instructions": assignment_payload["ground"]["transport_instructions"],
        "maps_attached": ", ".join(map_files),
        "debrief_attached": ", ".join(debrief_files),
        "equipment_issued": ", ".join(equipment_issued),
        "briefer": leader_name,
        "time_briefed": team_payload["briefed_ts"],
        "time_out": team_payload["enroute_ts"],
        "time_in": team_payload["complete_ts"] or team_payload["arrival_ts"],
        "notes": task_payload["description"] or assignment_payload["ground"]["present_search_efforts"],
        "resource_type": team_payload["resource_type"],
        "weather_summary": weather_payload.get("summary", ""),
    }


def list_incident_channels() -> List[Dict[str, Any]]:
    try:
        return _client().get(f"/api/incidents/{_iid()}/channels-plan")
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
    row_id = int(result.get("id") or 0)
    try:
        write_audit(
            "task.comms.add",
            {
                "task_id": int(task_id),
                "comm_id": row_id,
                "incident_channel_id": incident_channel_id,
                "function": function,
                "remarks": remarks,
            },
        )
    except Exception:
        pass
    return row_id


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
        try:
            write_audit("task.comms.update", {"task_id": int(task_id), "comm_id": int(comm_id), "changes": patch})
        except Exception:
            pass


def remove_task_comm(row_id: int) -> None:
    """Requires task_id to call the route. Callers must use remove_task_comm_for_task instead."""
    pass


def remove_task_comm_for_task(task_id: int, comm_id: int) -> None:
    _client().delete(f"{_base()}/tasks/{task_id}/comms/{comm_id}")
    try:
        write_audit("task.comms.remove", {"task_id": int(task_id), "comm_id": int(comm_id)})
    except Exception:
        pass


def list_task_debriefs(task_id: int) -> List[Dict[str, Any]]:
    try:
        return _client().get(f"{_base()}/tasks/{task_id}/debriefs")
    except Exception:
        return []


def create_debrief(task_id: int, sortie_number: str, debriefer_id: str, types: List[str],
                   team_id: Optional[int] = None) -> int:
    result = _client().post(f"{_base()}/tasks/{task_id}/debriefs", json={
        "sortie_number": sortie_number,
        "debriefer_id": debriefer_id,
        "types": list(types or []),
    })
    debrief_id = int(result.get("int_id") or 0)
    if team_id:
        try:
            from modules.operations.data.repository import ics214_log_entry
            sortie_label = f" (Sortie {sortie_number})" if sortie_number else ""
            ics214_log_entry("team", team_id,
                             f"Debrief completed for Task {task_id}{sortie_label}",
                             source="auto")
        except Exception:
            pass
    return debrief_id


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
        location_facility_id=doc.get("location_facility_id") or "",
        created_by=doc.get("created_by") or "",
        created_at=doc.get("created_at") or "",
        assigned_to=None,
        due_time=doc.get("due_time"),
        assignment=doc.get("assignment") or "",
        team_leader=doc.get("team_leader") or "",
        team_phone=doc.get("team_phone") or "",
    )
    teams = list_task_teams(task.id)
    return TaskDetail(task=task, teams=teams)


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
    try:
        from modules.operations.data.repository import ics214_log_entry
        ics214_log_entry("team", team_int_id, "Team created", source="auto")
    except Exception:
        pass
    return team_int_id


def add_task_team(task_id: int, team_id: Optional[int] = None, sortie_id: Optional[str] = None, primary: bool = False) -> int:
    result = _client().post(f"{_base()}/tasks/{task_id}/teams", json={
        "team_id": team_id,
        "sortie_id": sortie_id,
        "primary": primary,
        "changed_by": _active_user_display(),
    })
    tt_id = int(result.get("tt_id") or 0)
    actual_team_id = int(result.get("team_id") or team_id or 0) or None
    # Set team assignment status to "assigned" (fires its own ICS-214 auto entry)
    try:
        from modules.operations.data.repository import set_team_assignment_status, ics214_log_entry
        set_team_assignment_status(tt_id, "assigned")
        if actual_team_id:
            ics214_log_entry("team", actual_team_id, f"Assigned to Task {task_id}", source="auto")
        ics214_log_entry("task", int(task_id), f"Team {actual_team_id or tt_id} assigned to task", source="auto")
    except Exception:
        pass
    try:
        write_audit("task.team.add", {"task_id": int(task_id), "team_id": actual_team_id, "tt_id": tt_id, "sortie_id": sortie_id, "primary": primary})
    except Exception:
        pass
    return tt_id


def set_primary_team(task_id: int, tt_id: int) -> None:
    _client().patch(f"{_base()}/tasks/{task_id}/teams/{tt_id}/primary", json={"changed_by": _active_user_display()})


def update_sortie_id(tt_id: int, sortie_id: Optional[str]) -> None:
    # We need task_id — scan for the tt_id
    # Best effort: callers in task_detail_widget pass context that includes task_id
    # Stub for now — this would require a search endpoint or embedding task_id knowledge
    pass


def update_sortie_id_for_task(task_id: int, tt_id: int, sortie_id: Optional[str]) -> None:
    _client().patch(
        f"{_base()}/tasks/{task_id}/teams/{tt_id}/sortie",
        json={"sortie_id": sortie_id, "changed_by": _active_user_display()},
    )
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
    _client().delete(f"{_base()}/tasks/{task_id}/teams/{tt_id}", params={"changed_by": _active_user_display()})
    try:
        from modules.operations.data.repository import ics214_log_entry
        if team_id:
            ics214_log_entry("team", int(team_id), f"Removed from Task {task_id}", source="auto")
        ics214_log_entry("task", int(task_id), f"Team {team_id or tt_id} removed from task", source="auto")
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


def create_task(
    title: str = "<New Task>",
    task_identifier: Optional[str] = None,
    priority: Any = 2,
    status: str = "Draft",
    location: Optional[str] = None,
    location_facility_id: Optional[str] = None,
    description: Optional[str] = None,
) -> int:
    if isinstance(priority, str):
        priority_str = priority if priority in PRIORITY_MAP.values() else "Medium"
    else:
        priority_str = PRIORITY_MAP.get(priority, "Medium")
    body: Dict[str, Any] = {
        "title": title,
        "task_id": task_identifier,
        "priority": priority_str,
        "status": status,
    }
    if location:
        body["location"] = location
    if location_facility_id:
        body["location_facility_id"] = location_facility_id
    if description:
        body["assignment"] = description
    result = _client().post(f"{_base()}/tasks", json=body)
    return int(result.get("int_id") or 0)


# --- Planning linkage (objectives / strategies) -----------------------

def list_objectives() -> List[Dict[str, Any]]:
    """List incident objectives, for the Planning tab's Objective combo."""
    try:
        return _client().get("/api/objectives", params={"incident_id": _iid()}) or []
    except Exception:
        return []


def list_strategies_for_objective(objective_id: Optional[str]) -> List[Dict[str, Any]]:
    """List strategies (work assignments) under a given objective."""
    if not objective_id:
        return []
    try:
        return _client().get(
            f"/api/incidents/{_iid()}/planning/work-assignments",
            params={"objective_id": objective_id},
        ) or []
    except Exception:
        return []


def list_strategies_for_task(task_id: int) -> List[Dict[str, Any]]:
    """List strategies linked to this task, with their task-link id for removal."""
    try:
        return _client().get(f"/api/incidents/{_iid()}/planning/tasks/{task_id}/work-assignments") or []
    except Exception:
        return []


def link_task_to_strategy(task_id: int, work_assignment_id: int) -> None:
    _client().post(
        f"/api/incidents/{_iid()}/planning/work-assignments/{work_assignment_id}/task-links",
        json={"task_id": task_id, "link_type": "Linked Existing"},
    )
    try:
        write_audit("task.planning.link", {"task_id": int(task_id), "work_assignment_id": int(work_assignment_id)})
    except Exception:
        pass


def unlink_task_from_strategy(work_assignment_id: int, link_id: int) -> None:
    _client().delete(
        f"/api/incidents/{_iid()}/planning/work-assignments/{work_assignment_id}/task-links/{link_id}"
    )
    try:
        write_audit("task.planning.unlink", {"work_assignment_id": int(work_assignment_id), "link_id": int(link_id)})
    except Exception:
        pass
