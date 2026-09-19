"""Medical and ICS 206 API router for master and incident MongoDB data."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Query

from sarapp_db.mongo.collection_names import IncidentCollections, MasterCollections
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


class EMSAgenciesRepository(BaseRepository):
    collection_name = MasterCollections.EMS_AGENCIES
    soft_deletes = False


class Ics206AidStationsRepository(BaseRepository):
    collection_name = IncidentCollections.ICS_206_AID_STATIONS


class MedicalPlanRepository(BaseRepository):
    collection_name = IncidentCollections.MEDICAL_PLAN


def _normalize(doc: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(doc or {})
    data.pop("_id", None)
    return data


@router.get("/master/ems-agencies")
def list_ems_agencies(
    search: str = Query(""),
    include_inactive: bool = Query(True),
) -> list[dict[str, Any]]:
    repo = EMSAgenciesRepository(get_master_db())
    query: dict[str, Any] = {"deleted": {"$ne": True}}
    if not include_inactive:
        query["is_active"] = {"$ne": False}
    if search.strip():
        pattern = {"$regex": re.escape(search.strip()), "$options": "i"}
        query["$or"] = [
            {"name": pattern},
            {"type": pattern},
            {"phone": pattern},
            {"radio_channel": pattern},
            {"city": pattern},
            {"state": pattern},
        ]
    docs = repo.find_many(query, sort=[("name", 1)])
    return [_normalize(doc) for doc in docs]


def _served_versions(incident_id: str, op: int | None, version: int | None) -> dict[int, int]:
    """Map op_period -> version to serve.

    An explicit ``version`` applies to ``op``.  Otherwise each OP serves its
    latest *approved* version, falling back to its latest draft when nothing
    has been approved yet, so field devices never see a half-edited plan
    while an approved one exists.
    """
    repo = MedicalPlanRepository(get_incident_db(incident_id))
    query: dict[str, Any] = {"incident_id": incident_id}
    if op is not None:
        query["op_period"] = op
    latest: dict[int, int] = {}
    latest_approved: dict[int, int] = {}
    for doc in repo.find_many(query):
        doc_op = int(doc.get("op_period") or 0)
        doc_version = int(doc.get("version") or 1)
        latest[doc_op] = max(latest.get(doc_op, 0), doc_version)
        if doc.get("approval_status") == "approved":
            latest_approved[doc_op] = max(latest_approved.get(doc_op, 0), doc_version)
    served = {doc_op: latest_approved.get(doc_op, doc_latest) for doc_op, doc_latest in latest.items()}
    if op is not None and version is not None:
        served[op] = version
    return served


def _incident_query(incident_id: str, op: int | None = None, version: int | None = None) -> dict[str, Any]:
    query: dict[str, Any] = {"incident_id": incident_id}
    if op is not None:
        query["op_period"] = op
    if version is not None:
        query["version"] = version
    return query


def _incident_rows(
    repo_cls: type[BaseRepository],
    incident_id: str,
    op: int | None = None,
    version: int | None = None,
) -> list[dict[str, Any]]:
    repo = repo_cls(get_incident_db(incident_id))
    rows: list[dict[str, Any]] = []
    for op_period, op_version in sorted(_served_versions(incident_id, op, version).items()):
        docs = repo.find_many(_incident_query(incident_id, op_period, op_version), sort=[("id", 1)])
        rows.extend(_normalize(doc) for doc in docs)
    return rows


def _medical_plan(incident_id: str, op: int | None = None, version: int | None = None) -> dict[str, Any]:
    repo = MedicalPlanRepository(get_incident_db(incident_id))
    served = _served_versions(incident_id, op, version)
    if op is None:
        if not served:
            return {}
        op = min(served)
    if op not in served:
        return {}
    return _normalize(repo.find_one(_incident_query(incident_id, op, served[op])))


def _medical_plan_rows(
    incident_id: str, section: str, op: int | None = None, version: int | None = None
) -> list[dict[str, Any]]:
    repo = MedicalPlanRepository(get_incident_db(incident_id))
    plans = [
        _normalize(repo.find_one(_incident_query(incident_id, op_period, op_version)))
        for op_period, op_version in sorted(_served_versions(incident_id, op, version).items())
    ]
    output: list[dict[str, Any]] = []
    for plan in plans:
        rows = plan.get(section) or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            item = _normalize(row)
            if item.get("deleted"):
                continue
            item.setdefault("op_period", plan.get("op_period"))
            output.append(item)
    return sorted(output, key=lambda row: (int(row.get("op_period") or 0), int(row.get("id") or 0)))


def _medical_plan_single(
    incident_id: str, section: str, op: int | None = None, version: int | None = None
) -> dict[str, Any]:
    plan = _medical_plan(incident_id, op, version)
    value = plan.get(section) or {}
    if not isinstance(value, dict):
        return {}
    out = _normalize(value)
    out.setdefault("op_period", plan.get("op_period") or op)
    return out


@router.get("/incidents/{incident_id}/medical/ics206/aid-stations")
def list_ics206_aid_stations(
    incident_id: str, op: int | None = Query(None, ge=1), version: int | None = Query(None, ge=1)
) -> list[dict[str, Any]]:
    return _incident_rows(Ics206AidStationsRepository, incident_id, op, version)


@router.get("/incidents/{incident_id}/medical/ics206/ambulance-services")
def list_ics206_ambulance_services(
    incident_id: str, op: int | None = Query(None, ge=1), version: int | None = Query(None, ge=1)
) -> list[dict[str, Any]]:
    return _medical_plan_rows(incident_id, "ambulance_services", op, version)


@router.get("/incidents/{incident_id}/medical/ics206/hospitals")
def list_ics206_hospitals(incident_id: str, op: int | None = Query(None, ge=1), version: int | None = Query(None, ge=1)) -> list[dict[str, Any]]:
    return _medical_plan_rows(incident_id, "hospitals", op, version)


@router.get("/incidents/{incident_id}/medical/ics206/air-ambulance")
def list_ics206_air_ambulance(
    incident_id: str, op: int | None = Query(None, ge=1), version: int | None = Query(None, ge=1)
) -> list[dict[str, Any]]:
    return _medical_plan_rows(incident_id, "air_ambulance", op, version)


@router.get("/incidents/{incident_id}/medical/ics206/comms")
def list_ics206_medical_comms(
    incident_id: str, op: int | None = Query(None, ge=1), version: int | None = Query(None, ge=1)
) -> list[dict[str, Any]]:
    return _medical_plan_rows(incident_id, "medical_comms", op, version)


@router.get("/incidents/{incident_id}/medical/ics206/procedures")
def get_ics206_procedures(incident_id: str, op: int | None = Query(None, ge=1), version: int | None = Query(None, ge=1)) -> dict[str, Any]:
    return _medical_plan_single(incident_id, "procedures", op, version)


@router.get("/incidents/{incident_id}/medical/ics206/signatures")
def get_ics206_signatures(incident_id: str, op: int | None = Query(None, ge=1), version: int | None = Query(None, ge=1)) -> dict[str, Any]:
    return _medical_plan_single(incident_id, "signatures", op, version)
