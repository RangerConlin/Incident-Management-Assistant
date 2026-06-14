"""Operations teams data repository — proxies through SARApp API (MongoDB backend)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

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


def get_team(team_id: int) -> Optional[Team]:
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
    raw_leader = doc.get("team_leader") or doc.get("leader_personnel_id")
    try:
        leader_id = int(raw_leader) if raw_leader is not None else None
    except (ValueError, TypeError):
        leader_id = None
    return Team(
        team_id=int(doc.get("int_id") or team_id),
        name=doc.get("name") or f"Team {team_id}",
        callsign=doc.get("callsign"),
        role=doc.get("role"),
        priority=doc.get("priority"),
        team_leader_id=leader_id,
        team_leader_phone=doc.get("leader_phone") or doc.get("phone"),
        notes=doc.get("notes"),
        status=doc.get("status") or "available",
        current_task_id=doc.get("current_task_id"),
        location=doc.get("location"),
        team_type=doc.get("team_type") or "GT",
        readiness_status=doc.get("readiness_status") or "Unknown",
        last_comm_ts=comm_dt,
    )


def save_team(team: Team) -> Team:
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
        "team_type": getattr(team, "team_type", None),
        "readiness_status": getattr(team, "readiness_status", None),
    }
    data = {k: v for k, v in data.items() if v is not None}

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
        _client().patch(f"{_base()}/teams/{team_id}/comm-ping", json={"ts": ts})
    except Exception:
        pass


def find_team_ids_by_label(label: str) -> list[int]:
    if not label:
        return []
    try:
        results = _client().get(f"{_base()}/teams/search", params={"label": label.strip()})
        return [int(r.get("int_id") or 0) for r in results]
    except Exception:
        return []
