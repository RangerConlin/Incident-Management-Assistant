"""Mobile team-location tracking (GIS module Phase 1 — see tracking_plan.md
in ICS-Mobile-App for the full design).

No per-person location is ever stored. Every ping resolves the pinging
person's team (via that team's own roster) and writes straight onto the
team's own TEAMS document, gated by a leader-preference check: the team
leader's ping always wins; a non-leader's ping only takes over once the
leader is no longer the current source. Tracking is manual (start/stop),
never tied to login/logout.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException

from sarapp_db.mongo.collection_names import IncidentCollections, MasterCollections
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


class TeamsRepository(BaseRepository):
    collection_name = IncidentCollections.TEAMS
    soft_deletes = False


class ResourceStatusRepository(BaseRepository):
    collection_name = IncidentCollections.RESOURCE_STATUS


def _teams_repo(incident_id: str) -> TeamsRepository:
    return TeamsRepository(get_incident_db(incident_id))


def _resource_status_repo(incident_id: str) -> ResourceStatusRepository:
    return ResourceStatusRepository(get_incident_db(incident_id))


def _tokens_col():
    return get_master_db()[MasterCollections.PUSH_TOKENS]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_id_list(value: Any) -> list[int]:
    """Mirror operations.py's _parse_id_list for members_json parsing."""
    import json

    if value in (None, ""):
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return []
    if not isinstance(value, (list, tuple)):
        return []
    out: list[int] = []
    for item in value:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return out


def _resolve_person_and_incident(token: str) -> tuple[Optional[int], Optional[str]]:
    row = _tokens_col().find_one({"token": token})
    if not row:
        return None, None
    person_record = row.get("person_record")
    incident_id = row.get("incident_id")
    if person_record is None or not incident_id:
        return None, None
    return int(person_record), str(incident_id)


def _has_checked_in(incident_id: str, person_record: int) -> bool:
    """A person only counts as checked in if they have a resource_status
    (entity_type=personnel) record for this incident — mirrors checkin.py's
    own definition of "checked in"."""
    return (
        _resource_status_repo(incident_id).find_one(
            {"entity_type": "personnel", "record_id": person_record}
        )
        is not None
    )


def _team_for_person(incident_id: str, person_record: int) -> Optional[dict[str, Any]]:
    """Find the team whose roster (members_json) includes this person.

    Team membership, not the personnel check-in record, is the source of
    truth for "which team is this person on" — the check-in resource_status
    doc's `assigned_to` field is free-text planning-status data (can hold
    values like "Staging"), not a reliable team_id.
    """
    teams_repo = _teams_repo(incident_id)
    for team in teams_repo.find_many({}):
        member_ids = _parse_id_list(
            team.get("members_json")
            or team.get("member_person_records")
            or team.get("member_personnel_ids")
        )
        if person_record in member_ids:
            return team
    return None


def _team_leader_id(team_doc: dict[str, Any]) -> Optional[int]:
    """Mirror repository.py's get_team() leader-field precedence."""
    raw_leader = (
        team_doc.get("leader_person_record")
        or team_doc.get("team_leader")
        or team_doc.get("leader_personnel_id")
    )
    try:
        return int(raw_leader) if raw_leader is not None else None
    except (TypeError, ValueError):
        return None


@router.post("/location")
def submit_location(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    token = str(body.get("token") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="token is required")
    lat = body.get("lat")
    lon = body.get("lon")
    if lat is None or lon is None:
        raise HTTPException(status_code=400, detail="lat and lon are required")

    person_record, incident_id = _resolve_person_and_incident(token)
    if person_record is None or incident_id is None:
        return {"ok": True, "recorded": False}

    if not _has_checked_in(incident_id, person_record):
        return {"ok": True, "recorded": False}

    team_doc = _team_for_person(incident_id, person_record)
    if team_doc is None:
        return {"ok": True, "recorded": False}

    leader_id = _team_leader_id(team_doc)
    is_leader = leader_id is not None and leader_id == person_record
    current_source = team_doc.get("current_location_person_record")
    current_source_is_leader = (
        leader_id is not None and current_source is not None and int(current_source) == leader_id
    )

    if not is_leader and current_source_is_leader:
        # Leader is already the source for this team's dot — a non-leader
        # ping never displaces it.
        return {"ok": True, "recorded": False}

    updates = {
        "current_location_lat": lat,
        "current_location_lon": lon,
        "current_location_updated_at": body.get("timestamp") or _utcnow(),
        "current_location_person_record": person_record,
    }
    _teams_repo(incident_id).update_one(team_doc["_id"], updates)
    return {"ok": True, "recorded": True}


@router.post("/location/stop")
def stop_location(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    token = str(body.get("token") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="token is required")

    person_record, incident_id = _resolve_person_and_incident(token)
    if person_record is None or incident_id is None:
        return {"ok": True, "cleared": False}

    team_doc = _team_for_person(incident_id, person_record)
    if team_doc is None:
        return {"ok": True, "cleared": False}

    current_source = team_doc.get("current_location_person_record")
    if current_source is None or int(current_source) != person_record:
        # This device wasn't the current source for the team's dot — no
        # fallback search for another tracking member; tracking is manual.
        return {"ok": True, "cleared": False}

    _teams_repo(incident_id).update_one(
        team_doc["_id"],
        {
            "current_location_lat": None,
            "current_location_lon": None,
            "current_location_updated_at": None,
            "current_location_person_record": None,
        },
    )
    return {"ok": True, "cleared": True}
