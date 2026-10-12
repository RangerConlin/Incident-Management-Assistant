"""Medical and ICS 206 API router for master and incident MongoDB data."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from sarapp_db.mongo.collection_names import IncidentCollections, MasterCollections
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db
from sarapp_db.mongo.repository import BaseRepository
from sarapp_db.services.hospital_directory import SOURCE_LABEL as HOSPITAL_SOURCE_LABEL
from sarapp_db.services.hospital_directory import HospitalDirectory
from sarapp_db.services.nearby_medical import MAX_RADIUS_MI, NearbyLookupError, find_nearby
from sarapp_db.services.nearby_medical import SOURCE_LABEL as AMBULANCE_SOURCE_LABEL

NEARBY_KINDS = {"ambulance-services", "hospitals"}
_AMBULANCE_NOTE = (
    "Source data has names, addresses and locations only. Phone numbers and service level "
    "(ALS/BLS) are left blank - fill them in after adding."
)
_HOSPITAL_NOTE = (
    "Hospitals with emergency services, from CMS. Trauma level, helipad and burn center are not "
    "in the source - fill them in after adding."
)

router = APIRouter()


class EMSAgenciesRepository(BaseRepository):
    collection_name = MasterCollections.EMS_AGENCIES
    soft_deletes = False


class Ics206AidStationsRepository(BaseRepository):
    collection_name = IncidentCollections.ICS_206_AID_STATIONS


class MedicalPlanRepository(BaseRepository):
    collection_name = IncidentCollections.MEDICAL_PLAN


class NearbyFacilityExclusionsRepository(BaseRepository):
    collection_name = MasterCollections.NEARBY_FACILITY_EXCLUSIONS
    soft_deletes = False


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


@router.get("/medical/nearby/{kind}")
def nearby_medical_facilities(
    kind: str,
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius_mi: float = Query(25.0, gt=0, le=MAX_RADIUS_MI),
    refresh: bool = Query(False, description="Re-read the source before searching (hospitals only)"),
) -> dict[str, Any]:
    """Candidate ambulance services / ER hospitals near a point, nearest first.

    Returns ``{"results": [...], "warnings": [...], "note": str, "source": str}``.
    """
    if kind not in NEARBY_KINDS:
        raise HTTPException(404, f"Unknown facility kind: {kind}")
    warnings: list[str] = []
    try:
        if kind == "hospitals":
            rows, warnings = HospitalDirectory(get_master_db()).find_nearby(lat, lon, radius_mi, refresh=refresh)
            note, source = _HOSPITAL_NOTE, HOSPITAL_SOURCE_LABEL
        else:
            rows = find_nearby(kind, lat, lon, radius_mi)
            note, source = _AMBULANCE_NOTE, AMBULANCE_SOURCE_LABEL
    except NearbyLookupError as exc:
        raise HTTPException(502, str(exc)) from exc
    hidden = {
        doc["source_ref"]
        for doc in NearbyFacilityExclusionsRepository(get_master_db()).find_many({"kind": kind})
    }
    return {
        "results": [row for row in rows if row["source_ref"] not in hidden],
        "warnings": warnings,
        "note": note,
        "source": source,
    }


@router.get("/medical/nearby-exclusions")
def list_nearby_exclusions() -> list[dict[str, Any]]:
    docs = NearbyFacilityExclusionsRepository(get_master_db()).find_many({}, sort=[("name", 1)])
    return [{**_normalize(doc), "id": doc["_id"]} for doc in docs]


@router.post("/medical/nearby-exclusions", status_code=201)
def add_nearby_exclusion(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Hide a facility from every future nearby search (shared across incidents)."""
    source_ref = str(body.get("source_ref") or "").strip()
    kind = str(body.get("kind") or "").strip()
    if not source_ref or kind not in NEARBY_KINDS:
        raise HTTPException(422, "source_ref and a valid kind are required")
    repo = NearbyFacilityExclusionsRepository(get_master_db())
    if repo.find_one({"source_ref": source_ref}):
        raise HTTPException(409, "That facility is already hidden")
    doc = repo.insert_one({
        "source_ref": source_ref,
        "kind": kind,
        "name": str(body.get("name") or "").strip(),
        "address": str(body.get("address") or "").strip(),
        "reason": str(body.get("reason") or "").strip(),
        "excluded_by": str(body.get("excluded_by") or "").strip(),
    })
    return {**_normalize(doc), "id": doc["_id"]}


@router.delete("/medical/nearby-exclusions/{exclusion_id}", status_code=204)
def remove_nearby_exclusion(exclusion_id: str) -> None:
    if not NearbyFacilityExclusionsRepository(get_master_db()).delete_one(exclusion_id):
        raise HTTPException(404, "Exclusion not found")


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
