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


class Ics206AmbulanceServicesRepository(BaseRepository):
    collection_name = IncidentCollections.ICS_206_AMBULANCE_SERVICES


class Ics206HospitalsRepository(BaseRepository):
    collection_name = IncidentCollections.ICS_206_HOSPITALS


class Ics206AirAmbulanceRepository(BaseRepository):
    collection_name = IncidentCollections.ICS_206_AIR_AMBULANCE


class Ics206MedicalCommsRepository(BaseRepository):
    collection_name = IncidentCollections.ICS_206_MEDICAL_COMMS


class Ics206ProceduresRepository(BaseRepository):
    collection_name = IncidentCollections.ICS_206_PROCEDURES


class Ics206SignaturesRepository(BaseRepository):
    collection_name = IncidentCollections.ICS_206_SIGNATURES


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


def _incident_query(incident_id: str, op: int | None = None) -> dict[str, Any]:
    query: dict[str, Any] = {"incident_id": incident_id}
    if op is not None:
        query["op_period"] = op
    return query


def _incident_rows(
    repo_cls: type[BaseRepository],
    incident_id: str,
    op: int | None = None,
) -> list[dict[str, Any]]:
    repo = repo_cls(get_incident_db(incident_id))
    docs = repo.find_many(_incident_query(incident_id, op), sort=[("id", 1)])
    return [_normalize(doc) for doc in docs]


def _incident_single(
    repo_cls: type[BaseRepository],
    incident_id: str,
    op: int | None = None,
) -> dict[str, Any]:
    repo = repo_cls(get_incident_db(incident_id))
    doc = repo.find_one(_incident_query(incident_id, op))
    return _normalize(doc)


@router.get("/incidents/{incident_id}/medical/ics206/aid-stations")
def list_ics206_aid_stations(incident_id: str, op: int | None = Query(None, ge=1)) -> list[dict[str, Any]]:
    return _incident_rows(Ics206AidStationsRepository, incident_id, op)


@router.get("/incidents/{incident_id}/medical/ics206/ambulance-services")
def list_ics206_ambulance_services(
    incident_id: str, op: int | None = Query(None, ge=1)
) -> list[dict[str, Any]]:
    return _incident_rows(Ics206AmbulanceServicesRepository, incident_id, op)


@router.get("/incidents/{incident_id}/medical/ics206/hospitals")
def list_ics206_hospitals(incident_id: str, op: int | None = Query(None, ge=1)) -> list[dict[str, Any]]:
    return _incident_rows(Ics206HospitalsRepository, incident_id, op)


@router.get("/incidents/{incident_id}/medical/ics206/air-ambulance")
def list_ics206_air_ambulance(
    incident_id: str, op: int | None = Query(None, ge=1)
) -> list[dict[str, Any]]:
    return _incident_rows(Ics206AirAmbulanceRepository, incident_id, op)


@router.get("/incidents/{incident_id}/medical/ics206/comms")
def list_ics206_medical_comms(
    incident_id: str, op: int | None = Query(None, ge=1)
) -> list[dict[str, Any]]:
    return _incident_rows(Ics206MedicalCommsRepository, incident_id, op)


@router.get("/incidents/{incident_id}/medical/ics206/procedures")
def get_ics206_procedures(incident_id: str, op: int | None = Query(None, ge=1)) -> dict[str, Any]:
    return _incident_single(Ics206ProceduresRepository, incident_id, op)


@router.get("/incidents/{incident_id}/medical/ics206/signatures")
def get_ics206_signatures(incident_id: str, op: int | None = Query(None, ge=1)) -> dict[str, Any]:
    return _incident_single(Ics206SignaturesRepository, incident_id, op)
