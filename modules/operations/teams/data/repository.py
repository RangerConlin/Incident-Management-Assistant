"""Operations teams data repository — proxies through SARApp API (MongoDB backend)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from .team import Team


def _base() -> str:
    from utils import incident_context
    v = incident_context.get_active_incident_id()
    if not v:
        raise RuntimeError("No active incident")
    return f"/api/incidents/{v}/operations"


def _client():
    from utils.api_client import api_client
    return api_client


def _parse_json_list(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return []
        return list(parsed) if isinstance(parsed, list) else []
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def _parse_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_int_list(value: Any) -> list[int]:
    result: list[int] = []
    for item in _parse_json_list(value):
        parsed = _parse_int(item)
        if parsed is not None:
            result.append(parsed)
    return result


def _active_incident_id() -> Optional[str]:
    from utils import incident_context
    return incident_context.get_active_incident_id()


def _cached_team_doc(team_id: int) -> Optional[dict[str, Any]]:
    """Return the active incident cache's team document when available."""
    try:
        from utils.incident_cache import incident_cache

        active_id = _active_incident_id()
        if not active_id or incident_cache.incident_id != str(active_id):
            return None
        for doc in incident_cache.get_all("teams"):
            try:
                if int(doc.get("int_id") or 0) == int(team_id):
                    return dict(doc)
            except (TypeError, ValueError):
                continue
    except Exception:
        return None
    return None


def _cached_all_teams() -> Optional[list[dict[str, Any]]]:
    """Return every cached team document for the active incident, if loaded."""
    try:
        from utils.incident_cache import incident_cache

        active_id = _active_incident_id()
        if not active_id or incident_cache.incident_id != str(active_id):
            return None
        return incident_cache.get_all("teams")
    except Exception:
        return None


def _cached_personnel_phone(person_record: Any) -> str:
    """Best-effort phone lookup for a team leader from the cached incident roster.

    Mirrors the server's ``_resolve_leader`` fallback (operations.py), which
    fills in a missing team-level phone from the leader's personnel record.
    """
    if person_record in (None, ""):
        return ""
    try:
        from utils.incident_cache import incident_cache

        pid = int(person_record)
        for doc in incident_cache.get_all("incident_personnel"):
            try:
                if int(doc.get("person_record") or 0) == pid:
                    return str(doc.get("phone") or "")
            except (TypeError, ValueError):
                continue
    except Exception:
        return ""
    return ""


def get_team(team_id: int) -> Optional[Team]:
    doc = _cached_team_doc(team_id)
    if doc is None:
        try:
            doc = _client().get(f"{_base()}/teams/{team_id}")
        except Exception:
            return None
    if not doc:
        return None
    comm_ts = doc.get("last_comm_ping")
    try:
        from datetime import datetime as _dt
        comm_dt = _dt.fromisoformat(comm_ts) if comm_ts else None
    except Exception:
        comm_dt = None
    raw_leader = doc.get("leader_person_record") or doc.get("team_leader") or doc.get("leader_personnel_id")
    leader_id = _parse_int(raw_leader)
    current_task_id = _parse_int(doc.get("current_task_id"))
    members = _parse_int_list(doc.get("members_json") or doc.get("member_person_records") or doc.get("member_personnel_ids"))
    leader_phone = doc.get("leader_phone") or doc.get("phone") or _cached_personnel_phone(raw_leader)
    return Team(
        team_id=int(doc.get("int_id") or team_id),
        name=doc.get("name") or f"Team {team_id}",
        callsign=doc.get("callsign"),
        role=doc.get("role"),
        priority=doc.get("priority"),
        team_leader_id=leader_id,
        team_leader_phone=leader_phone,
        notes=doc.get("notes"),
        status=doc.get("status") or "available",
        current_task_id=current_task_id,
        location=doc.get("location"),
        members=members,
        vehicles=[str(x) for x in _parse_json_list(doc.get("vehicles_json") or doc.get("vehicle_ids"))],
        equipment=[str(x) for x in _parse_json_list(doc.get("equipment_json"))],
        aircraft=[str(x) for x in _parse_json_list(doc.get("aircraft_json") or doc.get("aircraft_ids"))],
        team_type=doc.get("team_type") or "GT",
        operational_unit_id=_parse_int(doc.get("operational_unit_id")),
        readiness_status=doc.get("readiness_status") or "Unknown",
        ci_status=doc.get("ci_status") or "Available",
        needs_attention=bool(doc.get("needs_attention")),
        last_comm_ts=comm_dt,
    )


def save_team(team: Team, *, clear_operational_unit: bool = False) -> Team:
    """Persist a team. ``clear_operational_unit=True`` explicitly clears chain
    of command (otherwise an absent/None operational_unit_id is filtered out
    below like every other unset field, which would leave the previous
    assignment in place rather than clearing it - and could let the server's
    AIR auto-slot logic in operations.py re-assign it on the next save)."""
    data = {
        "name": team.name,
        "callsign": getattr(team, "callsign", None),
        "role": getattr(team, "role", None),
        "priority": getattr(team, "priority", None),
        "team_leader": getattr(team, "team_leader_id", None),
        "leader_phone": getattr(team, "team_leader_phone", None),
        "notes": getattr(team, "notes", None),
        "status": getattr(team, "status", None),
        "location": getattr(team, "location", None),
        "members_json": json.dumps(list(getattr(team, "members", []) or [])),
        "vehicles_json": json.dumps(list(getattr(team, "vehicles", []) or [])),
        "equipment_json": json.dumps(list(getattr(team, "equipment", []) or [])),
        "aircraft_json": json.dumps(list(getattr(team, "aircraft", []) or [])),
        "team_type": getattr(team, "team_type", None),
        "readiness_status": getattr(team, "readiness_status", None),
        "ci_status": getattr(team, "ci_status", None) or "Available",
        "needs_attention": bool(getattr(team, "needs_attention", False)),
    }
    data = {k: v for k, v in data.items() if v is not None}
    operational_unit_id = getattr(team, "operational_unit_id", None)
    if operational_unit_id is not None or clear_operational_unit:
        data["operational_unit_id"] = operational_unit_id

    if team.team_id is None:
        result = _client().post(f"{_base()}/teams", json=data)
        team.team_id = int(result.get("int_id") or 0)
    else:
        _client().patch(f"{_base()}/teams/{team.team_id}", json=data)
    return team


def set_team_status(team_id: int, status_key: str) -> None:
    """Delegate to operations data repository (keeps ICS-214 and Qt signals in sync)."""
    from modules.operations.data.repository import set_team_status as _set
    _set(int(team_id), str(status_key))


def reset_team_comm_timer(team_id: int, when: datetime | None = None) -> None:
    ts = (when or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    try:
        _client().patch(f"{_base()}/teams/{team_id}/comm-ping", json={"when": ts})
    except Exception:
        pass


def set_team_needs_attention(team_id: int, active: bool) -> None:
    _client().patch(f"{_base()}/teams/{team_id}", json={"needs_attention": bool(active)})


def set_team_current_task(team_id: int, task_id: int | None) -> None:
    _client().patch(f"{_base()}/teams/{team_id}", json={"current_task_id": task_id})


def find_team_ids_by_label(label: str) -> list[int]:
    if not label:
        return []
    try:
        results = _client().get(f"{_base()}/teams/search", params={"label": label.strip()})
        return [int(r.get("int_id") or 0) for r in results]
    except Exception:
        return []


def _checkin_base() -> str:
    from utils import incident_context
    v = incident_context.get_active_incident_id()
    if not v:
        raise RuntimeError("No active incident")
    return f"/api/incidents/{v}/checkin"


# ---------------------------------------------------------------------------
# Team check-in / disband (ICS-211 workflow)
# ---------------------------------------------------------------------------


_DERIVED_CHECKED_IN_STATUSES = {
    "Available",
    "Assigned",
    "Out of Service",
    "Preparing for Demobilization",
    "Checked In",
}


def _is_checked_in_status(status: Any) -> bool:
    """Mirror checkin.py's `_is_checked_in_status`."""
    return str(status or "").strip() in _DERIVED_CHECKED_IN_STATUSES


def _teams_by_checkin_state(checked_in: bool, include_disbanded: bool) -> Optional[list[dict[str, Any]]]:
    """Filter cached `teams` docs the same way checkin.py's
    `/teams/checked-state` endpoint filters them, or None if the cache isn't
    loaded for the active incident."""
    cached = _cached_all_teams()
    if cached is None:
        return None
    rows: list[dict[str, Any]] = []
    for doc in cached:
        is_checked_in = _is_checked_in_status(doc.get("status"))
        if is_checked_in != checked_in:
            continue
        if not include_disbanded and doc.get("disbanded"):
            continue
        row = dict(doc)
        row["checked_in"] = is_checked_in
        row["disbanded"] = bool(doc.get("disbanded", False))
        rows.append(row)
    rows.sort(key=lambda d: str(d.get("name") or ""))
    return rows


def get_checked_in_teams() -> list[dict[str, Any]]:
    """List checked-in, non-disbanded teams for the Team Status Board."""
    cached = _teams_by_checkin_state(checked_in=True, include_disbanded=False)
    if cached is not None:
        return cached
    try:
        return _client().get(
            f"{_checkin_base()}/teams/checked-state",
            params={"checked_in": True, "include_disbanded": False},
        ) or []
    except Exception:
        return []


def get_unchecked_teams() -> list[dict[str, Any]]:
    """List teams that are not checked in (for planning/inbound views)."""
    cached = _teams_by_checkin_state(checked_in=False, include_disbanded=False)
    if cached is not None:
        return cached
    try:
        return _client().get(
            f"{_checkin_base()}/teams/checked-state",
            params={"checked_in": False, "include_disbanded": False},
        ) or []
    except Exception:
        return []


def check_in_team(
    team_id: int,
    *,
    keep_together: bool = True,
    checked_in_by: Optional[str] = None,
    checkin_notes: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Check in a team. If keep_together=False, also disband."""
    try:
        return _client().post(
            f"{_checkin_base()}/teams/{team_id}/checkin",
            json={
                "keep_together": keep_together,
                "checked_in_by": checked_in_by,
                "checkin_notes": checkin_notes,
            },
        )
    except Exception:
        return None


def disband_team(
    team_id: int,
    *,
    disbanded_by: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Disband a team (separate from check-in)."""
    try:
        return _client().post(
            f"{_checkin_base()}/teams/{team_id}/disband",
            json={"disbanded_by": disbanded_by},
        )
    except Exception:
        return None


def set_team_ci_status(team_id: int, ci_status: str) -> None:
    """Set a resource status on a team for planning visibility."""
    try:
        _client().patch(f"{_base()}/teams/{team_id}", json={"ci_status": ci_status})
    except Exception:
        pass
