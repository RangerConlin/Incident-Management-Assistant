"""Canonical ICS-214 activity-log API.

An incident owns one chronological pool of immutable entries. Entity logs are
filtered views over that pool, not stored streams. This is not an audit log.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.repository import BaseRepository
from sarapp_db.ics_reference import BUILTIN_LOG_KEYS, builtin_log_definitions

router = APIRouter()

ASSOCIATION_FIELDS = (
    "person_ids", "team_ids", "task_ids", "org_unit_ids", "facility_ids",
    "resource_ids", "external_agency_ids",
)


class Ics214EntriesRepository(BaseRepository):
    collection_name = IncidentCollections.ICS_214_ENTRIES
    soft_deletes = False


class Ics214LogDefinitionsRepository(BaseRepository):
    collection_name = IncidentCollections.ICS_214_LOG_DEFINITIONS
    soft_deletes = True


def _entries_repo(incident_id: str) -> Ics214EntriesRepository:
    return Ics214EntriesRepository(get_incident_db(incident_id))


def _definitions_repo(incident_id: str) -> Ics214LogDefinitionsRepository:
    return Ics214LogDefinitionsRepository(get_incident_db(incident_id))


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return str(uuid.uuid4())


def _normalize_ids(values: List[int]) -> List[int]:
    return sorted(set(values))


class Associations(BaseModel):
    person_ids: List[int] = Field(default_factory=list)
    team_ids: List[int] = Field(default_factory=list)
    task_ids: List[int] = Field(default_factory=list)
    org_unit_ids: List[int] = Field(default_factory=list)
    facility_ids: List[int] = Field(default_factory=list)
    resource_ids: List[int] = Field(default_factory=list)
    external_agency_ids: List[int] = Field(default_factory=list)

    @field_validator(*ASSOCIATION_FIELDS)
    @classmethod
    def validate_ids(cls, value: List[int]) -> List[int]:
        if any(item <= 0 for item in value):
            raise ValueError("association IDs must be positive integers")
        return _normalize_ids(value)

    def as_document(self) -> Dict[str, List[int]]:
        return {field: list(getattr(self, field)) for field in ASSOCIATION_FIELDS}


class SourceRecord(BaseModel):
    collection: str
    record_id: str


class EntryCreate(Associations):
    log_keys: List[str] = Field(default_factory=list)
    text: str = Field(min_length=1)
    occurred_at: Optional[datetime] = None
    critical_flag: bool = False
    incident_wide: bool = False
    source: str = "manual"
    created_by: Optional[str] = None
    source_record: Optional[SourceRecord] = None
    expand_team_members: bool = False
    idempotency_hash: Optional[str] = None

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return value

    @field_validator("log_keys")
    @classmethod
    def validate_log_keys(cls, value: List[str]) -> List[str]:
        normalized = sorted({item.strip() for item in value if item.strip()})
        unknown = set(normalized) - BUILTIN_LOG_KEYS
        if unknown:
            raise ValueError(f"unknown built-in log key(s): {', '.join(sorted(unknown))}")
        return normalized


class VoidRequest(BaseModel):
    voided_by: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class CorrectionCreate(EntryCreate):
    voided_by: str = Field(min_length=1)
    void_reason: str = Field(min_length=1)


class LogFilter(Associations):
    log_keys: List[str] = Field(default_factory=list)
    operational_period_id: Optional[int] = None
    incident_wide: Optional[bool] = None
    unassigned: bool = False
    include_voided: bool = False
    occurred_from: Optional[datetime] = None
    occurred_to: Optional[datetime] = None
    sources: List[str] = Field(default_factory=list)
    critical_only: bool = False


class LogDefinitionCreate(BaseModel):
    name: str = Field(min_length=1)
    filters: LogFilter
    unit_name: str = ""
    prepared_by_position: str = ""


class LogDefinitionUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    filters: Optional[LogFilter] = None
    unit_name: Optional[str] = None
    prepared_by_position: Optional[str] = None


def _team_member_ids(incident_id: str, team_ids: List[int]) -> List[int]:
    if not team_ids:
        return []
    teams = get_incident_db(incident_id)[IncidentCollections.TEAMS].find(
        {"int_id": {"$in": team_ids}}, {"member_person_records": 1, "members": 1}
    )
    result: set[int] = set()
    for team in teams:
        values = list(team.get("member_person_records") or [])
        values += [
            member.get("person_record") or member.get("person_id")
            for member in (team.get("members") or [])
        ]
        for value in values:
            try:
                if value is not None and int(value) > 0:
                    result.add(int(value))
            except (TypeError, ValueError):
                continue
    return sorted(result)


def _entry_document(incident_id: str, data: EntryCreate) -> Dict[str, Any]:
    occurred = data.occurred_at or datetime.now(timezone.utc)
    if occurred.tzinfo is None:
        occurred = occurred.replace(tzinfo=timezone.utc)
    associations = data.as_document()
    if data.expand_team_members:
        associations["person_ids"] = _normalize_ids(
            associations["person_ids"] + _team_member_ids(incident_id, associations["team_ids"])
        )
    entry_id = _new_id()
    return {
        "_id": entry_id,
        "entry_id": entry_id,
        "incident_id": incident_id,
        "text": data.text,
        "occurred_at": occurred.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "created_at": _utcnow(),
        "created_by": data.created_by,
        "source": data.source,
        "source_record": data.source_record.model_dump() if data.source_record else None,
        "critical_flag": data.critical_flag,
        "incident_wide": data.incident_wide,
        "log_keys": list(data.log_keys),
        **associations,
        "idempotency_hash": data.idempotency_hash
        or hashlib.sha256(f"manual:{uuid.uuid4()}".encode()).hexdigest(),
        "voided_at": None,
        "voided_by": None,
        "void_reason": None,
        "corrects_entry_id": None,
    }


def _map_entry(doc: Dict[str, Any]) -> Dict[str, Any]:
    result = {key: value for key, value in doc.items() if key != "_id"}
    result["id"] = doc.get("entry_id") or str(doc.get("_id", ""))
    result["unassigned"] = not bool(doc.get("incident_wide")) and not doc.get("log_keys") and not any(
        doc.get(field) for field in ASSOCIATION_FIELDS
    )
    result["voided"] = bool(doc.get("voided_at"))
    return result


def _insert_entry(incident_id: str, data: EntryCreate) -> Dict[str, Any]:
    repo = _entries_repo(incident_id)
    if data.idempotency_hash:
        existing = repo.find_one({
            "incident_id": incident_id,
            "idempotency_hash": data.idempotency_hash,
        })
        if existing:
            return _map_entry(existing)
    return _map_entry(repo.insert_one(_entry_document(incident_id, data)))


def _entry_query(incident_id: str, filters: LogFilter) -> Dict[str, Any]:
    query: Dict[str, Any] = {"incident_id": incident_id}
    if not filters.include_voided:
        query["voided_at"] = None
    if filters.log_keys:
        query["log_keys"] = {"$in": filters.log_keys}
    for field in ASSOCIATION_FIELDS:
        values = getattr(filters, field)
        if values:
            query[field] = {"$in": values}
    if filters.incident_wide is not None:
        query["incident_wide"] = filters.incident_wide
    if filters.unassigned:
        query["incident_wide"] = False
        query["log_keys"] = {"$size": 0}
        for field in ASSOCIATION_FIELDS:
            query[field] = {"$size": 0}
    occurred_from = filters.occurred_from
    occurred_to = filters.occurred_to
    if filters.operational_period_id is not None:
        period = get_incident_db(incident_id)[IncidentCollections.OPERATIONAL_PERIODS].find_one({
            "int_id": filters.operational_period_id,
            "deleted": {"$ne": True},
        })
        if not period:
            raise HTTPException(status_code=404, detail="Operational period not found")
        try:
            occurred_from = datetime.fromisoformat(str(period.get("start_time") or "").replace("Z", "+00:00"))
            occurred_to = datetime.fromisoformat(str(period.get("end_time") or "").replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Operational period has invalid boundaries") from exc
    if occurred_from or occurred_to:
        occurred: Dict[str, str] = {}
        if occurred_from:
            occurred["$gte"] = occurred_from.isoformat(timespec="seconds")
        if occurred_to:
            occurred["$lt"] = occurred_to.isoformat(timespec="seconds")
        query["occurred_at"] = occurred
    if filters.sources:
        query["source"] = {"$in": filters.sources}
    if filters.critical_only:
        query["critical_flag"] = True
    return query


def _option_rows(collection, id_field: str, label_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    rows = []
    for doc in collection.find({id_field: {"$exists": True}}):
        try:
            record_id = int(doc[id_field])
        except (TypeError, ValueError):
            continue
        label = next((str(doc.get(field) or "").strip() for field in label_fields
                      if str(doc.get(field) or "").strip()), f"Record {record_id}")
        rows.append({"id": record_id, "label": label, "archived": bool(doc.get("deleted"))})
    return sorted(rows, key=lambda row: (row["archived"], row["label"].lower(), row["id"]))


@router.get("/incidents/{incident_id}/ics214/association-options")
def association_options(incident_id: str):
    """Resolve permanent association IDs without storing labels on entries."""
    db = get_incident_db(incident_id)
    return {
        "person_ids": _option_rows(
            db[IncidentCollections.INCIDENT_PERSONNEL], "person_record",
            ("name", "display_name", "full_name", "person_id"),
        ),
        "team_ids": _option_rows(db[IncidentCollections.TEAMS], "int_id", ("name", "callsign")),
        "task_ids": _option_rows(db[IncidentCollections.TASKS], "int_id", ("title", "task_name")),
        "org_unit_ids": _option_rows(
            db[IncidentCollections.INCIDENT_ORG], "position_id", ("title", "name"),
        ),
        "facility_ids": _option_rows(db[IncidentCollections.FACILITIES], "int_id", ("name",)),
        "resource_ids": _option_rows(
            db[IncidentCollections.RESOURCE_STATUS], "int_id", ("resource_name", "resource_id"),
        ),
        "external_agency_ids": _option_rows(
            db[IncidentCollections.LIAISON_AGENCIES], "int_id", ("name", "agency_name"),
        ),
    }


@router.post("/incidents/{incident_id}/ics214/entries", status_code=201)
def create_entry(incident_id: str, data: EntryCreate):
    return _insert_entry(incident_id, data)


@router.get("/incidents/{incident_id}/ics214/entries")
def list_entries(
    incident_id: str,
    log_key: List[str] = Query(default=[]),
    person_id: List[int] = Query(default=[]),
    team_id: List[int] = Query(default=[]),
    task_id: List[int] = Query(default=[]),
    org_unit_id: List[int] = Query(default=[]),
    facility_id: List[int] = Query(default=[]),
    resource_id: List[int] = Query(default=[]),
    external_agency_id: List[int] = Query(default=[]),
    operational_period_id: Optional[int] = None,
    incident_wide: Optional[bool] = None,
    unassigned: bool = False,
    include_voided: bool = False,
    occurred_from: Optional[datetime] = None,
    occurred_to: Optional[datetime] = None,
    source: List[str] = Query(default=[]),
    critical_only: bool = False,
):
    filters = LogFilter(
        log_keys=log_key,
        person_ids=person_id, team_ids=team_id, task_ids=task_id,
        org_unit_ids=org_unit_id, facility_ids=facility_id,
        resource_ids=resource_id, external_agency_ids=external_agency_id,
        operational_period_id=operational_period_id,
        incident_wide=incident_wide, unassigned=unassigned,
        include_voided=include_voided, occurred_from=occurred_from,
        occurred_to=occurred_to, sources=source, critical_only=critical_only,
    )
    docs = _entries_repo(incident_id)._col.find(_entry_query(incident_id, filters)).sort(
        [("occurred_at", 1), ("created_at", 1)]
    )
    return [_map_entry(doc) for doc in docs]


@router.get("/incidents/{incident_id}/ics214/entries/{entry_id}")
def get_entry(incident_id: str, entry_id: str):
    doc = _entries_repo(incident_id).find_one({"incident_id": incident_id, "entry_id": entry_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Entry not found")
    return _map_entry(doc)


@router.post("/incidents/{incident_id}/ics214/entries/{entry_id}/void")
def void_entry(incident_id: str, entry_id: str, data: VoidRequest):
    repo = _entries_repo(incident_id)
    doc = repo.find_one({"incident_id": incident_id, "entry_id": entry_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Entry not found")
    if doc.get("voided_at"):
        raise HTTPException(status_code=409, detail="Entry is already voided")
    repo.update_one(doc["_id"], {
        "voided_at": _utcnow(), "voided_by": data.voided_by,
        "void_reason": data.reason,
    }, extra_filter={"incident_id": incident_id, "voided_at": None})
    return _map_entry(repo.find_by_id(doc["_id"]) or doc)


@router.post("/incidents/{incident_id}/ics214/entries/{entry_id}/correct", status_code=201)
def correct_entry(incident_id: str, entry_id: str, data: CorrectionCreate):
    repo = _entries_repo(incident_id)
    original = repo.find_one({"incident_id": incident_id, "entry_id": entry_id})
    if not original:
        raise HTTPException(status_code=404, detail="Entry not found")
    if original.get("voided_at"):
        raise HTTPException(status_code=409, detail="Entry is already voided")
    repo.update_one(original["_id"], {
        "voided_at": _utcnow(), "voided_by": data.voided_by,
        "void_reason": data.void_reason,
    }, extra_filter={"incident_id": incident_id, "voided_at": None})
    replacement = _entry_document(incident_id, data)
    replacement["corrects_entry_id"] = entry_id
    return _map_entry(repo.insert_one(replacement))


def _map_definition(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {**{key: value for key, value in doc.items() if key != "_id"},
            "id": doc.get("definition_id")}


@router.get("/incidents/{incident_id}/ics214/log-definitions")
def list_log_definitions(incident_id: str):
    custom = [_map_definition(doc) for doc in _definitions_repo(incident_id).find_many(
        {"incident_id": incident_id}, sort=[("name", 1)]
    )]
    return [*builtin_log_definitions(), *custom]


@router.post("/incidents/{incident_id}/ics214/log-definitions", status_code=201)
def create_log_definition(incident_id: str, data: LogDefinitionCreate):
    definition_id = _new_id()
    return _map_definition(_definitions_repo(incident_id).insert_one({
        "_id": definition_id, "definition_id": definition_id,
        "incident_id": incident_id, **data.model_dump(mode="json"),
    }))


@router.patch("/incidents/{incident_id}/ics214/log-definitions/{definition_id}")
def update_log_definition(incident_id: str, definition_id: str, data: LogDefinitionUpdate):
    if definition_id.startswith("builtin:"):
        raise HTTPException(status_code=405, detail="Built-in ICS logs are immutable")
    repo = _definitions_repo(incident_id)
    doc = repo.find_one({"incident_id": incident_id, "definition_id": definition_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Log definition not found")
    repo.update_one(doc["_id"], data.model_dump(exclude_unset=True, mode="json"),
                    extra_filter={"incident_id": incident_id})
    return _map_definition(repo.find_by_id(doc["_id"]) or doc)


@router.delete("/incidents/{incident_id}/ics214/log-definitions/{definition_id}", status_code=204)
def archive_log_definition(incident_id: str, definition_id: str):
    if definition_id.startswith("builtin:"):
        raise HTTPException(status_code=405, detail="Built-in ICS logs are immutable")
    repo = _definitions_repo(incident_id)
    doc = repo.find_one({"incident_id": incident_id, "definition_id": definition_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Log definition not found")
    repo.soft_delete(doc["_id"])


class MobileLogEntryCreate(BaseModel):
    text: str
    actor_user_id: Optional[str] = None
    occurred_at: Optional[datetime] = None
    timestamp_utc: Optional[datetime] = None
    critical_flag: bool = False


class MobileNarrativeCreate(MobileLogEntryCreate):
    pass


class TasksRepository(BaseRepository):
    collection_name = IncidentCollections.TASKS


@router.post("/incidents/{incident_id}/mobile/teams/{team_id}/log", status_code=201, tags=["mobile"])
def mobile_add_team_log_entry(incident_id: str, team_id: int, data: MobileLogEntryCreate):
    return _insert_entry(incident_id, EntryCreate(
        text=data.text, occurred_at=data.occurred_at or data.timestamp_utc,
        critical_flag=data.critical_flag, source="mobile",
        created_by=data.actor_user_id, team_ids=[team_id],
        expand_team_members=True,
    ))


@router.get("/incidents/{incident_id}/mobile/teams/{team_id}/log", tags=["mobile"])
def mobile_get_team_log(incident_id: str, team_id: int, since: Optional[datetime] = None):
    filters = LogFilter(team_ids=[team_id], occurred_from=since)
    docs = _entries_repo(incident_id)._col.find(_entry_query(incident_id, filters)).sort("occurred_at", 1)
    return [_map_entry(doc) for doc in docs if doc.get("source") != "internal"]


@router.post(
    "/incidents/{incident_id}/mobile/teams/{team_id}/tasks/{task_id}/narrative",
    status_code=201,
    tags=["mobile"],
)
def mobile_add_task_narrative(
    incident_id: str, team_id: int, task_id: int, data: MobileNarrativeCreate
):
    """Add the task narrative and one associated 214 entry."""
    tasks = TasksRepository(get_incident_db(incident_id))
    task = tasks.find_one({"int_id": task_id})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    occurred = data.occurred_at or data.timestamp_utc or datetime.now(timezone.utc)
    narrative_id = _new_id()
    narrative = {
        "id": narrative_id,
        "timestamp": occurred.isoformat(timespec="seconds"),
        "narrative": data.text,
        "entered_by": data.actor_user_id or "",
        "team_id": team_id,
        "critical": data.critical_flag,
        "source": "mobile",
    }
    tasks.apply_update(task["_id"], {"$push": {"narrative": narrative}})
    entry = _insert_entry(incident_id, EntryCreate(
        text=data.text, occurred_at=occurred, critical_flag=data.critical_flag,
        source="mobile", created_by=data.actor_user_id, team_ids=[team_id],
        task_ids=[task_id], expand_team_members=True,
        source_record=SourceRecord(collection=IncidentCollections.TASKS, record_id=str(task_id)),
        idempotency_hash=hashlib.sha256(f"mobile-narrative:{narrative_id}".encode()).hexdigest(),
    ))
    return {**narrative, "ics214_entry_id": entry["id"]}
