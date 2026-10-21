"""Team readiness validation + resource-conflict detection API (Stage 6).

Thin Mongo-reading wrapper around the framework-free
`sarapp_db.services.team_validation` module, which is the sole
authoritative source for team readiness -- see that module's docstring.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException

from sarapp_db.mongo.collection_names import IncidentCollections, MasterCollections
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db
from sarapp_db.mongo.int_id import _ensure_int_ids
from sarapp_db.mongo.repository import BaseRepository
from sarapp_db.services.team_validation import (
    RequirementSpec,
    TeamComposition,
    evaluate_team,
    find_conflicting_assignments,
)

router = APIRouter()


class _TeamsRepository(BaseRepository):
    collection_name = IncidentCollections.TEAMS
    soft_deletes = False


def _teams_repo(incident_id: str) -> _TeamsRepository:
    return _TeamsRepository(get_incident_db(incident_id))


def _parse_json_int_list(value: Any) -> list[int]:
    if not value:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return []
    result = []
    for item in value or []:
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            continue
    return result


# (resource_type key, master collection, record field, the team doc's own
# JSON-array field name -- operations.py's create_team only pluralizes
# "vehicles_json"; "equipment_json"/"aircraft_json" stay singular).
_ASSET_FIELDS: tuple[tuple[str, str], ...] = (
    ("vehicle", "vehicles_json"),
    ("aircraft", "aircraft_json"),
    ("equipment", "equipment_json"),
)
_ASSET_COLLECTIONS = {
    "vehicle": (MasterCollections.VEHICLES, "vehicle_record"),
    "aircraft": (MasterCollections.AIRCRAFT, "aircraft_record"),
    "equipment": (MasterCollections.EQUIPMENT, "equipment_record"),
}


def _team_refs(team_doc: dict[str, Any]) -> list[tuple[str, int]]:
    refs: list[tuple[str, int]] = []
    for pid in _parse_json_int_list(team_doc.get("member_person_records")):
        refs.append(("personnel", pid))
    for kind, json_field in _ASSET_FIELDS:
        for rid in _parse_json_int_list(team_doc.get(json_field)):
            refs.append((kind, rid))
    return refs


def _requirement_spec(resource_type_doc: dict[str, Any] | None) -> RequirementSpec | None:
    if resource_type_doc is None:
        return None
    return RequirementSpec(
        min_personnel=resource_type_doc.get("min_personnel"),
        required_qualifications=list(resource_type_doc.get("required_qualifications") or []),
        required_equipment_type_ids=[
            int(x) for x in (resource_type_doc.get("required_equipment_ids") or [])
        ],
    )


def _person_qualifications(master_db, person_record: int) -> set[str]:
    """Best-effort set of qualification names/codes a person holds, used
    to match against a Resource Type Library's free-text
    `required_qualifications`. Combines their role field with any
    certification names resolvable from certification_types."""
    person = master_db[MasterCollections.PERSONNEL].find_one({"person_record": person_record})
    if not person:
        return set()
    names: set[str] = set()
    for field in ("primary_role", "role", "rank"):
        value = person.get(field)
        if value:
            names.add(str(value))
    for cert in person.get("certifications") or []:
        cert_type_id = cert.get("certification_type_id") or cert.get("cert_type_id")
        if cert_type_id is None:
            continue
        cert_type = master_db[MasterCollections.CERTIFICATION_TYPES].find_one({"id": cert_type_id})
        if cert_type and cert_type.get("name"):
            names.add(str(cert_type["name"]))
    return names


def _assigned_resource_type_ids(master_db, team_doc: dict[str, Any]) -> list[int]:
    ids: list[int] = []
    for kind, json_field in _ASSET_FIELDS:
        collection_name, record_field = _ASSET_COLLECTIONS[kind]
        for rid in _parse_json_int_list(team_doc.get(json_field)):
            doc = master_db[collection_name].find_one({record_field: rid})
            rt_id = (doc or {}).get("resource_type_id")
            if rt_id is not None:
                try:
                    ids.append(int(rt_id))
                except (TypeError, ValueError):
                    pass
    return ids


def _other_teams_with_refs(incident_id: str, exclude_team_id: int) -> list[dict[str, Any]]:
    repo = _teams_repo(incident_id)
    out = []
    for doc in repo.find_many({"int_id": {"$ne": exclude_team_id}}):
        out.append(
            {
                "team_id": doc.get("int_id"),
                "team_name": doc.get("name"),
                "disbanded": bool(doc.get("disbanded")),
                "refs": _team_refs(doc),
            }
        )
    return out


@router.get("/incidents/{incident_id}/operations/teams/{team_id}/validation")
def validate_team(incident_id: str, team_id: int) -> dict[str, Any]:
    repo = _teams_repo(incident_id)
    _ensure_int_ids(repo._col)
    team_doc = repo.find_one({"int_id": team_id})
    if team_doc is None:
        raise HTTPException(status_code=404, detail=f"Team {team_id} not found")

    master_db = get_master_db()

    resource_type_doc = None
    resource_type_id = team_doc.get("resource_type_id")
    if resource_type_id is not None:
        resource_type_doc = master_db[MasterCollections.RESOURCE_TYPES].find_one(
            {"resource_type_id": str(resource_type_id)}
        )

    personnel_ids = _parse_json_int_list(team_doc.get("member_person_records"))
    composition = TeamComposition(
        personnel_ids=personnel_ids,
        personnel_qualifications={pid: _person_qualifications(master_db, pid) for pid in personnel_ids},
        vehicle_ids=_parse_json_int_list(team_doc.get("vehicles_json")),
        aircraft_ids=_parse_json_int_list(team_doc.get("aircraft_json")),
        equipment_ids=_parse_json_int_list(team_doc.get("equipment_json")),
        assigned_resource_type_ids=_assigned_resource_type_ids(master_db, team_doc),
        conflicts=find_conflicting_assignments(
            team_id, _team_refs(team_doc), _other_teams_with_refs(incident_id, team_id)
        ),
    )
    result = evaluate_team(_requirement_spec(resource_type_doc), composition)
    payload = result.to_dict()
    payload["team_id"] = team_id
    payload["resource_type_id"] = resource_type_id
    return payload
