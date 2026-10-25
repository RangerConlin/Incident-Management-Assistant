"""Mobile incident entry and participation context.

The router returns incident facts only.  The mobile client decides which
experience to display from the presence or absence of a team assignment.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from sarapp_db.api.routers import checkin
from sarapp_db.mongo.collection_names import IncidentCollections, MasterCollections
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


class TeamsRepository(BaseRepository):
    collection_name = IncidentCollections.TEAMS
    soft_deletes = False


class IncidentOrgRepository(BaseRepository):
    collection_name = IncidentCollections.INCIDENT_ORG
    soft_deletes = False


class IncidentPersonnelRepository(BaseRepository):
    collection_name = IncidentCollections.INCIDENT_PERSONNEL
    soft_deletes = False


class ResourceStatusRepository(BaseRepository):
    collection_name = IncidentCollections.RESOURCE_STATUS


class MobileEntryRequest(BaseModel):
    person_record: int
    team_id: int | None = None


def _strip(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if doc is None:
        return None
    result = dict(doc)
    result.pop("_id", None)
    return result


def _active_team_query(person_record: int) -> dict[str, Any]:
    return {
        "member_person_records": int(person_record),
        "disbanded": {"$ne": True},
        "deleted": {"$ne": True},
    }


def _find_team(incident_id: str, person_record: int) -> dict[str, Any] | None:
    return TeamsRepository(get_incident_db(incident_id)).find_one(
        _active_team_query(person_record)
    )


def _staff_assignments(incident_id: str, person_record: int) -> list[dict[str, Any]]:
    repo = IncidentOrgRepository(get_incident_db(incident_id))
    docs = repo.find_many(
        {
            "$or": [
                {"primary.person_record": person_record},
                {"deputies.person_record": person_record},
                {"staff_assistants.person_record": person_record},
            ]
        },
        sort=[("position_id", 1)],
    )
    rows: list[dict[str, Any]] = []
    for doc in docs:
        for bucket, default_type in (
            ("primary", "primary"),
            ("deputies", "deputy"),
            ("staff_assistants", "staff_assistant"),
        ):
            for assignment in doc.get(bucket) or []:
                if assignment.get("person_record") != person_record or assignment.get("end_time") is not None:
                    continue
                rows.append(
                    {
                        "position_id": doc.get("position_id"),
                        "title": doc.get("title") or "",
                        "classification": doc.get("classification") or "",
                        "assignment_type": "trainee" if assignment.get("trainee") else default_type,
                        "start_time": assignment.get("start_time"),
                    }
                )
    return rows


def _context(incident_id: str, person_record: int) -> dict[str, Any]:
    db = get_incident_db(incident_id)
    person = IncidentPersonnelRepository(db).find_one({"person_record": person_record})
    status = ResourceStatusRepository(db).find_one(
        {
            "entity_type": "personnel",
            "record_id": person_record,
            "deleted": {"$ne": True},
        }
    )
    team = _find_team(incident_id, person_record)
    team_payload = None
    if team is not None:
        team_payload = {
            "team_id": team.get("int_id"),
            "team_name": team.get("name") or team.get("callsign") or "",
            "team_role": team.get("role") or "",
            "is_leader": team.get("team_leader") == person_record,
        }
    return {
        "person": _strip(person),
        "resource_status": _strip(status),
        "team": team_payload,
        "staff_assignments": _staff_assignments(incident_id, person_record),
    }


def _require_master_person(person_record: int) -> None:
    person = get_master_db()[MasterCollections.PERSONNEL].find_one(
        {"person_record": person_record, "deleted": {"$ne": True}}
    )
    if person is None:
        raise HTTPException(404, "Personnel record not found")


def _assign_team(incident_id: str, person_record: int, team_id: int) -> None:
    repo = TeamsRepository(get_incident_db(incident_id))
    target = repo.find_one({"int_id": team_id, "deleted": {"$ne": True}})
    if target is None:
        raise HTTPException(404, f"Team {team_id} not found")

    current = repo.find_one(_active_team_query(person_record))
    if current is not None and current.get("_id") != target.get("_id"):
        repo.apply_update(
            current["_id"],
            {"$pull": {"member_person_records": person_record}},
        )
    repo.apply_update(
        target["_id"],
        {"$addToSet": {"member_person_records": person_record}},
    )

    status_repo = ResourceStatusRepository(get_incident_db(incident_id))
    status = status_repo.find_one(
        {"entity_type": "personnel", "record_id": person_record}
    )
    if status is not None:
        status_repo.update_one(
            status["_id"],
            {"assigned_to": team_id, "assignment_reference": team_id},
        )


@router.post("/{incident_id}/mobile/entry")
def enter_incident(
    incident_id: str,
    body: MobileEntryRequest = Body(...),
) -> dict[str, Any]:
    """Enter an incident and return the person's current participation facts."""
    _require_master_person(body.person_record)
    db = get_incident_db(incident_id)
    status_repo = ResourceStatusRepository(db)
    existing = status_repo.find_one(
        {
            "entity_type": "personnel",
            "record_id": body.person_record,
            "deleted": {"$ne": True},
        }
    )

    if existing is None:
        current_team = _find_team(incident_id, body.person_record)
        entry_team_id = body.team_id
        if entry_team_id is None and current_team is not None:
            entry_team_id = current_team.get("int_id")
        checkin.save_checkin(
            incident_id,
            body.person_record,
            {
                "status": "Checked In",
                "team_id": entry_team_id,
            },
        )
    if body.team_id is not None:
        _assign_team(incident_id, body.person_record, body.team_id)

    return _context(incident_id, body.person_record)


@router.get("/{incident_id}/mobile/context/{person_record}")
def get_mobile_context(incident_id: str, person_record: int) -> dict[str, Any]:
    """Return identity, status, team, and staff-position facts for mobile."""
    _require_master_person(person_record)
    return _context(incident_id, person_record)
