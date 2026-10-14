"""Medical and ICS 206 API router for master and incident MongoDB data."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from itertools import combinations
from math import asin, ceil, cos, radians, sin, sqrt
from typing import Any, Mapping

from fastapi import APIRouter, Body, HTTPException, Query

from sarapp_db.mongo.collection_names import IncidentCollections, MasterCollections
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db
from sarapp_db.mongo.repository import BaseRepository
from sarapp_db.services.hospital_directory import SOURCE_LABEL as HOSPITAL_SOURCE_LABEL
from sarapp_db.services.hospital_directory import HospitalDirectory
from sarapp_db.services.nearby_medical import MAX_RADIUS_MI, NearbyLookupError, find_nearby
from sarapp_db.services.nearby_medical import SOURCE_LABEL as AMBULANCE_SOURCE_LABEL

logger = logging.getLogger(__name__)

EMS_AGENCY_TYPES = ("Ground Ambulance", "Air Ambulance", "Other")
_EMS_PHONE_SANITISE_RE = re.compile(r"\D+")
_EMS_NAME_SANITISE_RE = re.compile(r"[^A-Z0-9]+")

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


class EMSAgencyAuditLogRepository(BaseRepository):
    collection_name = MasterCollections.EMS_AGENCY_AUDIT_LOG
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


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ems_repo() -> EMSAgenciesRepository:
    return EMSAgenciesRepository(get_master_db())


def _ems_audit_repo() -> EMSAgencyAuditLogRepository:
    return EMSAgencyAuditLogRepository(get_master_db())


def _ems_write_audit(action: str, detail: dict[str, Any]) -> None:
    try:
        _ems_audit_repo().insert_one(
            {
                "ts_utc": _utcnow(),
                "action": action,
                "detail": detail,
                "entity_type": "ems_agency",
                "entity_id": detail.get("id") or detail.get("survivor"),
            }
        )
    except Exception:  # pragma: no cover - audit failures should not block CRUD
        logger.exception("Failed to write EMS agency audit entry for %s", action)


def _next_ems_agency_id(repo: EMSAgenciesRepository) -> int:
    docs = repo.find_many({}, sort=[("id", -1)], limit=1)
    doc = docs[0] if docs else None
    return int(doc["id"]) + 1 if doc and doc.get("id") is not None else 1


def _sanitize_ems_phone(value: str) -> str:
    cleaned = value.replace(";", "/").replace(",", "/")
    cleaned = re.sub(r"\s*[/]\s*", " / ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _normalize_ems_phone(value: str | None) -> str:
    if not value:
        return ""
    return _EMS_PHONE_SANITISE_RE.sub("", value)


def _normalize_ems_name(value: str | None) -> str:
    if not value:
        return ""
    return _EMS_NAME_SANITISE_RE.sub("", value.upper().strip())


def _prepare_ems_payload(payload: dict[str, Any], *, creating: bool) -> dict[str, Any]:
    data: dict[str, Any] = {}
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(422, "Name is required")
    data["name"] = name

    type_value = str(payload.get("type") or "").strip()
    if type_value not in EMS_AGENCY_TYPES:
        raise HTTPException(422, "Type is required")
    data["type"] = type_value

    phone = payload.get("phone") or ""
    data["phone"] = _sanitize_ems_phone(phone) if phone else None

    for field in ("radio_channel", "address", "city", "state", "zip", "notes"):
        data[field] = str(payload.get(field) or "").strip() or None

    for field in ("lat", "lon"):
        raw = payload.get(field)
        if raw in (None, ""):
            data[field] = None
            continue
        try:
            data[field] = float(raw)
        except (TypeError, ValueError) as exc:
            raise HTTPException(422, f"{field.upper()} must be a number") from exc

    data["default_on_206"] = bool(payload.get("default_on_206"))
    is_active = payload.get("is_active")
    if creating:
        data["is_active"] = is_active in (None, "", True, 1)
    elif is_active is not None:
        data["is_active"] = bool(is_active)
    return data


@router.get("/master/ems-agencies")
def list_ems_agencies(
    search: str = Query(""),
    include_inactive: bool = Query(True),
    ids: str = Query(""),
) -> list[dict[str, Any]]:
    repo = _ems_repo()
    query: dict[str, Any] = {"deleted": {"$ne": True}}
    if not include_inactive:
        query["is_active"] = {"$ne": False}
    if ids.strip():
        try:
            id_values = sorted({int(value) for value in ids.split(",") if value.strip()})
        except ValueError as exc:
            raise HTTPException(422, "ids must be a comma-separated list of integers") from exc
        if not id_values:
            return []
        query["id"] = {"$in": id_values}
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


@router.get("/master/ems-agencies/duplicates")
def list_ems_agency_duplicates() -> list[dict[str, Any]]:
    """Group EMS agencies that look like duplicates (shared phone or near-identical name)."""
    rows = [_normalize(doc) for doc in _ems_repo().find_many({"deleted": {"$ne": True}}, sort=[("name", 1)])]
    by_id = {int(row["id"]): row for row in rows if row.get("id") is not None}
    groups: list[set[int]] = []

    def _merge_group(new_ids: set[int]) -> None:
        merged = set(new_ids)
        keep: list[set[int]] = []
        for existing in groups:
            if existing & merged:
                merged |= existing
            else:
                keep.append(existing)
        keep.append(merged)
        groups[:] = keep

    phone_groups: dict[str, set[int]] = {}
    for row in rows:
        phone_key = _normalize_ems_phone(row.get("phone"))
        if len(phone_key) >= 7:
            phone_groups.setdefault(phone_key, set()).add(int(row["id"]))
    for id_set in phone_groups.values():
        if len(id_set) > 1:
            _merge_group(id_set)

    for a, b in combinations(by_id.values(), 2):
        name_a = _normalize_ems_name(a.get("name"))
        name_b = _normalize_ems_name(b.get("name"))
        if not name_a or not name_b:
            continue
        if name_a == name_b or SequenceMatcher(None, name_a, name_b).ratio() >= 0.9:
            _merge_group({int(a["id"]), int(b["id"])})

    result: list[dict[str, Any]] = []
    for id_set in groups:
        members = [by_id[i] for i in sorted(id_set)]
        reason = (
            "Shared phone"
            if any(
                len(_normalize_ems_phone(m.get("phone"))) >= 7
                and _normalize_ems_phone(m.get("phone")) == _normalize_ems_phone(members[0].get("phone"))
                for m in members
            )
            else "Similar name"
        )
        result.append({"candidate_ids": sorted(id_set), "reason": reason, "members": members})
    return result


@router.get("/master/ems-agencies/audit-log")
def list_ems_agency_audit_log(
    limit: int = Query(250, ge=1, le=1000),
    start: str | None = Query(None),
    end: str | None = Query(None),
    user: str | None = Query(None),
    action: str | None = Query(None),
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {"action": {"$regex": r"^ems_agency\."}}
    if start or end:
        query["ts_utc"] = {}
        if start:
            query["ts_utc"]["$gte"] = start
        if end:
            query["ts_utc"]["$lte"] = end
    if action:
        query["action"] = action
    if user:
        query["user_id"] = {"$regex": re.escape(user), "$options": "i"}
    docs = _ems_audit_repo().find_many(query, sort=[("ts_utc", -1)], limit=limit)
    return [_normalize(doc) for doc in docs]


@router.get("/master/ems-agencies/{agency_id}")
def get_ems_agency(agency_id: int) -> dict[str, Any]:
    doc = _ems_repo().find_one({"id": agency_id, "deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(404, "EMS agency not found")
    return _normalize(doc)


@router.post("/master/ems-agencies", status_code=201)
def create_ems_agency(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _ems_repo()
    data = _prepare_ems_payload(body, creating=True)
    now = _utcnow()
    new_id = _next_ems_agency_id(repo)
    data["id"] = new_id
    data["created_at"] = now
    data["updated_at"] = now
    data["deleted"] = False
    doc = repo.insert_one(data)
    normalized = _normalize(doc)
    _ems_write_audit("ems_agency.create", {"id": new_id, "data": normalized})
    return normalized


@router.patch("/master/ems-agencies/{agency_id}")
def update_ems_agency(agency_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _ems_repo()
    existing = repo.find_one({"id": agency_id, "deleted": {"$ne": True}})
    if not existing:
        raise HTTPException(404, "EMS agency not found")
    data = _prepare_ems_payload(body, creating=False)
    changes: dict[str, Any] = {}
    updates: dict[str, Any] = {}
    for key, value in data.items():
        if existing.get(key) != value:
            updates[key] = value
            changes[key] = {"old": existing.get(key), "new": value}
    if updates:
        repo.update_one(existing["_id"], updates)
        _ems_write_audit("ems_agency.update", {"id": agency_id, "changes": changes})
    return _normalize(repo.find_by_id(existing["_id"]))


@router.post("/master/ems-agencies/{agency_id}/active")
def set_ems_agency_active(agency_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _ems_repo()
    existing = repo.find_one({"id": agency_id, "deleted": {"$ne": True}})
    if not existing:
        raise HTTPException(404, "EMS agency not found")
    active = bool(body.get("active"))
    if bool(existing.get("is_active")) != active:
        repo.update_one(existing["_id"], {"is_active": active})
        _ems_write_audit(
            "ems_agency.restore" if active else "ems_agency.deactivate",
            {"id": agency_id, "previous": bool(existing.get("is_active")), "active": active},
        )
    return _normalize(repo.find_by_id(existing["_id"]))


@router.post("/master/ems-agencies/merge")
def merge_ems_agencies(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _ems_repo()
    survivor_id = body.get("survivor_id")
    if survivor_id is None:
        raise HTTPException(422, "survivor_id is required")
    survivor_id = int(survivor_id)
    duplicate_ids = sorted({int(value) for value in body.get("duplicate_ids") or [] if int(value) != survivor_id})
    for duplicate_id in duplicate_ids:
        existing = repo.find_one({"id": duplicate_id})
        if existing:
            repo.update_one(existing["_id"], {"is_active": False})
    if duplicate_ids:
        _ems_write_audit("ems_agency.merge", {"survivor": survivor_id, "merged": duplicate_ids})
    return {"survivor_id": survivor_id, "merged": duplicate_ids}


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


# ---------------------------------------------------------------------------
# Editable ICS-206 plan API — the live working copy the desktop ICS-206 panel
# edits (as opposed to the "served" read endpoints above, which resolve to
# whichever version is approved/latest for display and export).  Every write
# here is explicit about (op, version); `version` defaults to the latest
# version on record for that op when omitted.
# ---------------------------------------------------------------------------

APPROVAL_NOT_STARTED = "not_started"
APPROVAL_PENDING = "pending"
APPROVAL_APPROVED = "approved"
APPROVAL_REJECTED = "rejected"
APPROVAL_LABELS = {
    APPROVAL_NOT_STARTED: "Draft",
    APPROVAL_PENDING: "In review",
    APPROVAL_APPROVED: "Approved",
    APPROVAL_REJECTED: "Rejected",
}

PLAN_TABLE_FIELDS: dict[str, tuple[str, ...]] = {
    "ambulance_services": (
        "id", "op_period", "source_ref", "name", "type", "service_level", "phone", "location", "notes",
    ),
    "hospitals": (
        "id", "op_period", "source_ref", "name", "address", "phone", "helipad", "burn_center", "level",
        "adult_trauma_level", "pediatric_trauma_level", "lat", "lon", "travel_time_min",
        "travel_time_air_min", "travel_time_ground_min", "notes",
    ),
    "air_ambulance": ("id", "op_period", "name", "phone", "base", "contact", "notes"),
    "medical_comms": ("id", "op_period", "channel", "function", "frequency", "mode", "notes"),
}
PLAN_TABLES = set(PLAN_TABLE_FIELDS)
AID_STATION_FIELDS: tuple[str, ...] = (
    "id", "op_period", "version", "facility_id", "name", "type", "level", "contact_frequency",
    "is_24_7", "location_text", "latitude", "longitude", "manager_personnel_id", "manager_name", "notes",
)


class IncidentProfileRepository(BaseRepository):
    collection_name = IncidentCollections.INCIDENT_PROFILE
    soft_deletes = False


class FacilitiesRepository(BaseRepository):
    collection_name = IncidentCollections.FACILITIES
    soft_deletes = False


class RadioChannelsRepository(BaseRepository):
    collection_name = MasterCollections.RADIO_CHANNELS
    soft_deletes = False


class MasterHospitalsRepository(BaseRepository):
    collection_name = MasterCollections.HOSPITALS
    soft_deletes = False


def _med_plan_repo(incident_id: str) -> MedicalPlanRepository:
    return MedicalPlanRepository(get_incident_db(incident_id))


def _med_aid_repo(incident_id: str) -> Ics206AidStationsRepository:
    return Ics206AidStationsRepository(get_incident_db(incident_id))


def _med_plan_docs(incident_id: str, op: int) -> list[dict[str, Any]]:
    return _med_plan_repo(incident_id).find_many(
        {"incident_id": incident_id, "op_period": op}, sort=[("version", 1)]
    )


def _med_latest_version(incident_id: str, op: int) -> int:
    docs = _med_plan_docs(incident_id, op)
    return max((int(doc.get("version") or 1) for doc in docs), default=1)


def _med_resolve_version(op: int, version: int | None, incident_id: str) -> int:
    return int(version) if version is not None else _med_latest_version(incident_id, op)


def _med_plan_id(incident_id: str, op: int, version: int) -> str:
    return f"{incident_id}-MEDICAL-PLAN-{int(op)}-V{int(version)}"


def _med_empty_plan(
    incident_id: str,
    op: int,
    version: int,
    prepared_name: str = "",
    prepared_personnel_id: str = "",
    prepared_position: str = "",
) -> dict[str, Any]:
    now = _utcnow()
    return {
        "plan_id": _med_plan_id(incident_id, op, version),
        "incident_id": incident_id,
        "op_period": op,
        "version": version,
        "approval_status": APPROVAL_NOT_STARTED,
        "change_note": "",
        "ambulance_services": [],
        "hospitals": [],
        "air_ambulance": [],
        "medical_comms": [],
        "procedures": {"id": 1, "op_period": op, "content": ""},
        "signatures": {
            "id": 1,
            "op_period": op,
            "prepared_by": prepared_name,
            "prepared_by_id": prepared_personnel_id,
            "position": prepared_position,
            "prepared_at": now,
            "date": now,
            "approved_by": "",
            "approved_by_id": "",
            "approved_by_position": "",
            "approved_at": "",
        },
        "deleted": False,
    }


def _med_ensure_plan(
    incident_id: str,
    op: int,
    version: int,
    *,
    prepared_name: str = "",
    prepared_personnel_id: str = "",
    prepared_position: str = "",
) -> dict[str, Any]:
    repo = _med_plan_repo(incident_id)
    doc = repo.find_one({"incident_id": incident_id, "op_period": op, "version": version})
    if doc:
        return doc
    return repo.insert_one(
        _med_empty_plan(incident_id, op, version, prepared_name, prepared_personnel_id, prepared_position)
    )


def _med_assert_editable(doc: Mapping[str, Any], version: int) -> None:
    status = str(doc.get("approval_status") or APPROVAL_NOT_STARTED)
    if status != APPROVAL_NOT_STARTED:
        label = APPROVAL_LABELS.get(status, status).lower()
        raise HTTPException(409, f"Version {version} is {label} and locked. Create a new version to make changes.")


def _med_normalize_plan(doc: Mapping[str, Any]) -> dict[str, Any]:
    out = _normalize(dict(doc))
    for table in PLAN_TABLES:
        rows = out.get(table) or []
        out[table] = [row for row in rows if isinstance(row, dict) and not row.get("deleted")]
    return out


def _med_icp_coordinates(incident_id: str) -> tuple[float | None, float | None]:
    db = get_incident_db(incident_id)
    profile = IncidentProfileRepository(db).find_one({"incident_id": incident_id}) or {}
    facility_id = str(profile.get("icp_facility_id") or "")
    if facility_id:
        facilities = FacilitiesRepository(db)
        facility = facilities.find_one({"id": facility_id}) or facilities.find_one({"_id": facility_id}) or {}
        lat = _med_float_or_none(facility.get("latitude"))
        lon = _med_float_or_none(facility.get("longitude"))
        if lat is not None and lon is not None:
            return lat, lon
    return _med_float_or_none(profile.get("latitude")), _med_float_or_none(profile.get("longitude"))


def _med_float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _med_haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_miles = 3958.8
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    r_lat1 = radians(lat1)
    r_lat2 = radians(lat2)
    a = sin(d_lat / 2) ** 2 + cos(r_lat1) * cos(r_lat2) * sin(d_lon / 2) ** 2
    return 2 * radius_miles * asin(sqrt(a))


def _med_travel_minutes(distance_miles: float, speed_mph: float) -> int:
    if distance_miles <= 0 or speed_mph <= 0:
        return 0
    return max(1, int(ceil((distance_miles / speed_mph) * 60)))


def _med_with_hospital_travel_times(incident_id: str, row: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(row)
    hospital_lat = _med_float_or_none(out.get("lat") or out.get("latitude"))
    hospital_lon = _med_float_or_none(out.get("lon") or out.get("longitude"))
    icp_lat, icp_lon = _med_icp_coordinates(incident_id)
    if None in (icp_lat, icp_lon, hospital_lat, hospital_lon):
        return out
    distance = _med_haversine_miles(float(icp_lat), float(icp_lon), float(hospital_lat), float(hospital_lon))
    ground_minutes = _med_travel_minutes(distance, 35.0)
    air_minutes = _med_travel_minutes(distance, 120.0)
    out["travel_time_ground_min"] = ground_minutes
    out["travel_time_air_min"] = air_minutes
    out["travel_time_min"] = out.get("travel_time_min") or ground_minutes
    return out


def _med_service_level_from_row(row: Mapping[str, Any]) -> int:
    raw = row.get("service_level")
    try:
        if raw is not None and raw != "":
            level = int(raw)
            if level in (0, 1, 2):
                return level
    except (TypeError, ValueError):
        pass
    type_value = str(row.get("type") or "").strip().lower()
    if "als" in type_value:
        return 2
    if "bls" in type_value:
        return 1
    return 0


def _med_trauma_level_int(value: Any) -> int:
    if value in (None, "", 0, "0", False):
        return 0
    if isinstance(value, int):
        return max(0, min(value, 5))
    text = str(value).strip().upper()
    return {"I": 1, "1": 1, "II": 2, "2": 2, "III": 3, "3": 3, "IV": 4, "4": 4, "V": 5, "5": 5}.get(text, 0)


def _med_trauma_display(adult_level: int, pediatric_level: int) -> str:
    roman = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V"}
    adult = roman.get(adult_level, "")
    pediatric = roman.get(pediatric_level, "")
    if adult and pediatric:
        return f"A-{adult} / P-{pediatric}"
    if adult:
        return adult
    if pediatric:
        return f"P-{pediatric}"
    return ""


def _med_next_plan_row_id(rows: list[dict[str, Any]]) -> int:
    return max((int(row.get("id") or 0) for row in rows), default=0) + 1


def _med_add_plan_row(
    incident_id: str, table: str, op: int, version: int, payload: Mapping[str, Any]
) -> dict[str, Any]:
    doc = _med_ensure_plan(incident_id, op, version)
    _med_assert_editable(doc, version)
    rows = [row for row in (doc.get(table) or []) if isinstance(row, dict)]
    fields = [f for f in PLAN_TABLE_FIELDS[table] if f not in ("id", "op_period", "version")]
    now = _utcnow()
    row = {"id": _med_next_plan_row_id(rows), "deleted": False, "created_at": now, "updated_at": now}
    row.update({field: payload.get(field) for field in fields})
    if table == "hospitals":
        row = _med_with_hospital_travel_times(incident_id, row)
    rows.append(row)
    _med_plan_repo(incident_id).update_one(doc["_id"], {table: rows})
    return row


def _med_next_aid_station_id(incident_id: str) -> int:
    docs = _med_aid_repo(incident_id).find_many({}, sort=[("id", -1)], limit=1)
    doc = docs[0] if docs else None
    return int(doc["id"]) + 1 if doc and doc.get("id") is not None else 1


def _med_add_aid_station_row(
    incident_id: str, op: int, version: int, payload: Mapping[str, Any]
) -> dict[str, Any]:
    doc = _med_ensure_plan(incident_id, op, version)
    _med_assert_editable(doc, version)
    fields = [f for f in AID_STATION_FIELDS if f not in ("id", "op_period", "version")]
    now = _utcnow()
    row = {
        "id": _med_next_aid_station_id(incident_id),
        "incident_id": incident_id,
        "op_period": op,
        "version": version,
        "deleted": False,
        "created_at": now,
        "updated_at": now,
    }
    row.update({field: payload.get(field) for field in fields})
    _med_aid_repo(incident_id).insert_one(row)
    return row


def _med_copy_aid_stations(
    incident_id: str, source_op: int, source_version: int, target_op: int, target_version: int
) -> None:
    repo = _med_aid_repo(incident_id)
    now = _utcnow()
    sources = repo.find_many({
        "incident_id": incident_id,
        "op_period": source_op,
        "version": source_version,
        "deleted": {"$ne": True},
    })
    next_id = _med_next_aid_station_id(incident_id)
    for source in sources:
        doc = {
            field: source.get(field)
            for field in AID_STATION_FIELDS
            if field not in ("id", "op_period", "version")
        }
        doc.update({
            "id": next_id,
            "incident_id": incident_id,
            "op_period": target_op,
            "version": target_version,
            "deleted": False,
            "created_at": now,
            "updated_at": now,
        })
        repo.insert_one(doc)
        next_id += 1


def _med_fresh_signatures(op: int, person: Mapping[str, Any], now: str) -> dict[str, Any]:
    return {
        "id": 1,
        "op_period": op,
        "prepared_by": str(person.get("name") or ""),
        "prepared_by_id": str(person.get("personnel_id") or ""),
        "position": str(person.get("position") or ""),
        "prepared_at": now,
        "date": now,
        "approved_by": "",
        "approved_by_id": "",
        "approved_by_position": "",
        "approved_at": "",
    }


def _med_build_version_copy(
    incident_id: str,
    source: Mapping[str, Any],
    op: int,
    version: int,
    change_note: str,
    person: Mapping[str, Any],
    now: str,
) -> dict[str, Any]:
    plan = _normalize(dict(source))
    plan.update({
        "plan_id": _med_plan_id(incident_id, op, version),
        "incident_id": incident_id,
        "op_period": op,
        "version": version,
        "approval_status": APPROVAL_NOT_STARTED,
        "change_note": change_note,
        "deleted": False,
        "created_at": now,
        "updated_at": now,
    })
    for table in PLAN_TABLES:
        plan[table] = [
            {**row, "op_period": op, "deleted": False, "created_at": now, "updated_at": now}
            for row in (source.get(table) or [])
            if isinstance(row, dict) and not row.get("deleted")
        ]
    plan["procedures"] = {**dict(source.get("procedures") or {}), "op_period": op, "updated_at": now}
    plan["signatures"] = _med_fresh_signatures(op, person, now)
    return plan


@router.get("/incidents/{incident_id}/medical/plan")
def get_medical_plan_edit(
    incident_id: str,
    op: int = Query(..., ge=1),
    version: int | None = Query(None, ge=1),
    prepared_name: str = Query(""),
    prepared_personnel_id: str = Query(""),
    prepared_position: str = Query(""),
) -> dict[str, Any]:
    v = _med_resolve_version(op, version, incident_id)
    doc = _med_ensure_plan(
        incident_id,
        op,
        v,
        prepared_name=prepared_name,
        prepared_personnel_id=prepared_personnel_id,
        prepared_position=prepared_position,
    )
    return _med_normalize_plan(doc)


@router.get("/incidents/{incident_id}/medical/plan/versions")
def list_medical_plan_versions(incident_id: str, op: int = Query(..., ge=1)) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for doc in _med_plan_docs(incident_id, op):
        sig = doc.get("signatures") if isinstance(doc.get("signatures"), dict) else {}
        out.append({
            "version": int(doc.get("version") or 1),
            "approval_status": str(doc.get("approval_status") or APPROVAL_NOT_STARTED),
            "change_note": str(doc.get("change_note") or ""),
            "created_at": str(doc.get("created_at") or ""),
            "prepared_by": str(sig.get("prepared_by") or ""),
            "prepared_at": str(sig.get("prepared_at") or ""),
            "approved_by": str(sig.get("approved_by") or ""),
            "approved_at": str(sig.get("approved_at") or ""),
        })
    return out


@router.post("/incidents/{incident_id}/medical/plan/new-version", status_code=201)
def create_medical_plan_new_version(
    incident_id: str,
    body: dict[str, Any] = Body(...),
    op: int = Query(..., ge=1),
    version: int | None = Query(None, ge=1),
) -> dict[str, Any]:
    v = _med_resolve_version(op, version, incident_id)
    source = _med_ensure_plan(incident_id, op, v)
    new_version = _med_latest_version(incident_id, op) + 1
    change_note = str(body.get("change_note") or "").strip()
    person = body.get("person") or {}
    now = _utcnow()
    plan = _med_build_version_copy(incident_id, source, op, new_version, change_note, person, now)
    _med_plan_repo(incident_id).insert_one(plan)
    _med_copy_aid_stations(incident_id, op, v, op, new_version)
    return {"version": new_version}


@router.post("/incidents/{incident_id}/medical/plan/duplicate-last-op")
def duplicate_medical_plan_last_op(
    incident_id: str,
    body: dict[str, Any] = Body(...),
    op: int = Query(..., ge=1),
    version: int | None = Query(None, ge=1),
) -> dict[str, Any]:
    v = _med_resolve_version(op, version, incident_id)
    target = _med_ensure_plan(incident_id, op, v)
    _med_assert_editable(target, v)
    previous = _med_plan_repo(incident_id).find_many(
        {"incident_id": incident_id, "op_period": {"$lt": op}},
        sort=[("op_period", -1), ("version", -1)],
        limit=1,
    )
    if not previous:
        return {"duplicated": False}
    source = previous[0]
    source_op = int(source["op_period"])
    source_version = int(source.get("version") or 1)
    person = body.get("person") or {}
    now = _utcnow()
    copy = _med_build_version_copy(
        incident_id, source, op, v, str(target.get("change_note") or ""), person, now
    )
    copy.pop("created_at", None)
    _med_plan_repo(incident_id).update_one(target["_id"], copy)
    aid_repo = _med_aid_repo(incident_id)
    for existing in aid_repo.find_many(
        {"incident_id": incident_id, "op_period": op, "version": v, "deleted": {"$ne": True}}
    ):
        aid_repo.update_one(existing["_id"], {"deleted": True})
    _med_copy_aid_stations(incident_id, source_op, source_version, op, v)
    return {"duplicated": True}


@router.patch("/incidents/{incident_id}/medical/plan/procedures")
def save_medical_plan_procedures(
    incident_id: str,
    body: dict[str, Any] = Body(...),
    op: int = Query(..., ge=1),
    version: int | None = Query(None, ge=1),
) -> dict[str, Any]:
    v = _med_resolve_version(op, version, incident_id)
    doc = _med_ensure_plan(incident_id, op, v)
    _med_assert_editable(doc, v)
    procedures = {
        "id": 1,
        "op_period": op,
        "content": str(body.get("content") or ""),
        "deleted": False,
        "updated_at": _utcnow(),
    }
    _med_plan_repo(incident_id).update_one(doc["_id"], {"procedures": procedures})
    return procedures


@router.patch("/incidents/{incident_id}/medical/plan/status")
def set_medical_plan_status(
    incident_id: str,
    body: dict[str, Any] = Body(...),
    op: int = Query(..., ge=1),
    version: int | None = Query(None, ge=1),
) -> dict[str, Any]:
    v = _med_resolve_version(op, version, incident_id)
    doc = _med_ensure_plan(incident_id, op, v)
    _med_assert_editable(doc, v)
    status = str(body.get("status") or "")
    if status != APPROVAL_PENDING:
        raise HTTPException(422, "Only 'pending' is supported here")
    _med_plan_repo(incident_id).update_one(doc["_id"], {"approval_status": APPROVAL_PENDING})
    return {"approval_status": APPROVAL_PENDING}


@router.post("/incidents/{incident_id}/medical/plan/approval")
def apply_medical_plan_approval(
    incident_id: str,
    body: dict[str, Any] = Body(...),
    op: int = Query(..., ge=1),
    version: int | None = Query(None, ge=1),
) -> dict[str, Any]:
    outcome = str(body.get("outcome") or "")
    if outcome not in (APPROVAL_APPROVED, APPROVAL_REJECTED):
        raise HTTPException(422, f"Not a final approval outcome: {outcome}")
    v = _med_resolve_version(op, version, incident_id)
    doc = _med_ensure_plan(incident_id, op, v)
    updates: dict[str, Any] = {"approval_status": outcome}
    if outcome == APPROVAL_APPROVED:
        person = body.get("person") or {}
        if not person.get("name"):
            raise HTTPException(422, "No signed-in user; cannot record an approver.")
        signatures = dict(doc.get("signatures") or {})
        signatures.update({
            "approved_by": person.get("name", ""),
            "approved_by_id": person.get("personnel_id", ""),
            "approved_by_position": person.get("position", ""),
            "approved_at": _utcnow(),
        })
        updates["signatures"] = signatures
    _med_plan_repo(incident_id).update_one(doc["_id"], updates)
    return _med_normalize_plan(_med_plan_repo(incident_id).find_by_id(doc["_id"]))


@router.post("/incidents/{incident_id}/medical/plan/{table}", status_code=201)
def add_medical_plan_row(
    incident_id: str,
    table: str,
    body: dict[str, Any] = Body(...),
    op: int = Query(..., ge=1),
    version: int | None = Query(None, ge=1),
) -> dict[str, Any]:
    if table not in PLAN_TABLES:
        raise HTTPException(404, f"Unknown plan table: {table}")
    v = _med_resolve_version(op, version, incident_id)
    return _med_add_plan_row(incident_id, table, op, v, body)


@router.patch("/incidents/{incident_id}/medical/plan/{table}/{row_id}")
def update_medical_plan_row(
    incident_id: str,
    table: str,
    row_id: int,
    body: dict[str, Any] = Body(...),
    op: int = Query(..., ge=1),
    version: int | None = Query(None, ge=1),
) -> dict[str, Any]:
    if table not in PLAN_TABLES:
        raise HTTPException(404, f"Unknown plan table: {table}")
    v = _med_resolve_version(op, version, incident_id)
    doc = _med_ensure_plan(incident_id, op, v)
    _med_assert_editable(doc, v)
    rows = [row for row in (doc.get(table) or []) if isinstance(row, dict)]
    fields = [f for f in PLAN_TABLE_FIELDS[table] if f not in ("id", "op_period", "version")]
    updated_row: dict[str, Any] | None = None
    for row in rows:
        if int(row.get("id") or 0) == int(row_id):
            for field in fields:
                if field in body:
                    row[field] = body.get(field)
            row["updated_at"] = _utcnow()
            if table == "hospitals":
                row = _med_with_hospital_travel_times(incident_id, row)
            updated_row = row
            break
    if updated_row is None:
        raise HTTPException(404, "Row not found")
    rows = [updated_row if int(row.get("id") or 0) == int(row_id) else row for row in rows]
    _med_plan_repo(incident_id).update_one(doc["_id"], {table: rows})
    return updated_row


@router.delete("/incidents/{incident_id}/medical/plan/{table}/{row_id}", status_code=204)
def delete_medical_plan_row(
    incident_id: str,
    table: str,
    row_id: int,
    op: int = Query(..., ge=1),
    version: int | None = Query(None, ge=1),
) -> None:
    if table not in PLAN_TABLES:
        raise HTTPException(404, f"Unknown plan table: {table}")
    v = _med_resolve_version(op, version, incident_id)
    doc = _med_ensure_plan(incident_id, op, v)
    _med_assert_editable(doc, v)
    rows = [row for row in (doc.get(table) or []) if isinstance(row, dict)]
    matched = False
    for row in rows:
        if int(row.get("id") or 0) == int(row_id):
            row["deleted"] = True
            row["updated_at"] = _utcnow()
            matched = True
            break
    if not matched:
        raise HTTPException(404, "Row not found")
    _med_plan_repo(incident_id).update_one(doc["_id"], {table: rows})


@router.post("/incidents/{incident_id}/medical/plan/{table}/import")
def import_medical_plan_table(
    incident_id: str,
    table: str,
    op: int = Query(..., ge=1),
    version: int | None = Query(None, ge=1),
) -> dict[str, int]:
    if table not in PLAN_TABLES:
        raise HTTPException(404, f"Unknown plan table: {table}")
    v = _med_resolve_version(op, version, incident_id)
    master_db = get_master_db()
    count = 0
    if table == "ambulance_services":
        rows = EMSAgenciesRepository(master_db).find_many(
            {"type": {"$in": ["Ground Ambulance", "Ambulance", "Air Ambulance"]}, "is_active": {"$ne": False}}
        )
        for raw in rows:
            row = _normalize(raw)
            _med_add_plan_row(incident_id, table, op, v, {
                "name": row.get("name"),
                "type": row.get("type"),
                "service_level": _med_service_level_from_row(row),
                "phone": row.get("phone"),
                "location": row.get("address"),
                "notes": row.get("notes"),
            })
            count += 1
    elif table == "hospitals":
        rows = MasterHospitalsRepository(master_db).find_many({"deleted": {"$ne": True}})
        for raw in rows:
            row = _normalize(raw)
            adult_level = _med_trauma_level_int(row.get("adult_trauma_level") or row.get("trauma_level"))
            pediatric_level = _med_trauma_level_int(row.get("pediatric_trauma_level"))
            if pediatric_level == 0 and row.get("pediatric_capability") and adult_level:
                pediatric_level = adult_level
            _med_add_plan_row(incident_id, table, op, v, {
                "name": row.get("name"),
                "address": row.get("address"),
                "phone": row.get("phone") or row.get("phone_er") or row.get("phone_switchboard"),
                "helipad": 1 if row.get("helipad") else 0,
                "burn_center": 1 if row.get("burn_center") else 0,
                "level": _med_trauma_display(adult_level, pediatric_level),
                "adult_trauma_level": adult_level,
                "pediatric_trauma_level": pediatric_level,
                "lat": row.get("lat"),
                "lon": row.get("lon"),
                "notes": row.get("notes"),
            })
            count += 1
    elif table == "air_ambulance":
        rows = EMSAgenciesRepository(master_db).find_many({"type": "Air Ambulance", "is_active": {"$ne": False}})
        for raw in rows:
            row = _normalize(raw)
            _med_add_plan_row(incident_id, table, op, v, {
                "name": row.get("name"),
                "phone": row.get("phone"),
                "base": row.get("address"),
                "contact": row.get("contact") or row.get("contact_name"),
                "notes": row.get("notes"),
            })
            count += 1
    else:  # medical_comms
        rows = RadioChannelsRepository(master_db).find_many({"deleted": {"$ne": True}})
        for raw in rows:
            row = _normalize(raw)
            _med_add_plan_row(incident_id, table, op, v, {
                "channel": row.get("alpha_tag") or row.get("channel_name"),
                "function": row.get("function"),
                "frequency": row.get("freq_rx") or row.get("frequency"),
                "mode": row.get("mode"),
                "notes": row.get("notes"),
            })
            count += 1
    return {"count": count}


@router.get("/incidents/{incident_id}/medical/aid-stations")
def list_medical_aid_stations(
    incident_id: str, op: int = Query(..., ge=1), version: int | None = Query(None, ge=1)
) -> list[dict[str, Any]]:
    v = _med_resolve_version(op, version, incident_id)
    rows = _med_aid_repo(incident_id).find_many(
        {"incident_id": incident_id, "op_period": op, "version": v, "deleted": {"$ne": True}}, sort=[("id", 1)]
    )
    return [_normalize(row) for row in rows]


@router.post("/incidents/{incident_id}/medical/aid-stations", status_code=201)
def create_medical_aid_station(
    incident_id: str,
    body: dict[str, Any] = Body(...),
    op: int = Query(..., ge=1),
    version: int | None = Query(None, ge=1),
) -> dict[str, Any]:
    v = _med_resolve_version(op, version, incident_id)
    return _med_add_aid_station_row(incident_id, op, v, body)


@router.patch("/incidents/{incident_id}/medical/aid-stations/{row_id}")
def update_medical_aid_station(
    incident_id: str,
    row_id: int,
    body: dict[str, Any] = Body(...),
    op: int = Query(..., ge=1),
    version: int | None = Query(None, ge=1),
) -> dict[str, Any]:
    v = _med_resolve_version(op, version, incident_id)
    doc = _med_ensure_plan(incident_id, op, v)
    _med_assert_editable(doc, v)
    repo = _med_aid_repo(incident_id)
    existing = repo.find_one({"id": int(row_id), "incident_id": incident_id})
    if not existing:
        raise HTTPException(404, "Aid station not found")
    fields = [f for f in AID_STATION_FIELDS if f not in ("id", "op_period", "version")]
    updates = {field: body.get(field) for field in fields if field in body}
    repo.update_one(existing["_id"], updates)
    return _normalize(repo.find_by_id(existing["_id"]))


@router.delete("/incidents/{incident_id}/medical/aid-stations/{row_id}", status_code=204)
def delete_medical_aid_station(
    incident_id: str,
    row_id: int,
    op: int = Query(..., ge=1),
    version: int | None = Query(None, ge=1),
) -> None:
    v = _med_resolve_version(op, version, incident_id)
    doc = _med_ensure_plan(incident_id, op, v)
    _med_assert_editable(doc, v)
    repo = _med_aid_repo(incident_id)
    existing = repo.find_one({"id": int(row_id), "incident_id": incident_id})
    if not existing:
        raise HTTPException(404, "Aid station not found")
    repo.update_one(existing["_id"], {"deleted": True})


@router.post("/incidents/{incident_id}/medical/aid-stations/import")
def import_medical_aid_stations(
    incident_id: str,
    op: int = Query(..., ge=1),
    version: int | None = Query(None, ge=1),
) -> dict[str, int]:
    v = _med_resolve_version(op, version, incident_id)
    rows = EMSAgenciesRepository(get_master_db()).find_many({"type": "Medical Aid", "is_active": {"$ne": False}})
    count = 0
    for raw in rows:
        row = _normalize(raw)
        _med_add_aid_station_row(incident_id, op, v, {
            "facility_id": "",
            "name": row.get("name"),
            "type": row.get("type"),
            "level": "",
            "contact_frequency": row.get("phone") or row.get("radio_channel") or "",
            "is_24_7": 0,
            "location_text": row.get("address") or "",
            "latitude": row.get("latitude"),
            "longitude": row.get("longitude"),
            "manager_personnel_id": "",
            "manager_name": row.get("contact") or row.get("contact_name") or "",
            "notes": row.get("notes"),
        })
        count += 1
    return {"count": count}
