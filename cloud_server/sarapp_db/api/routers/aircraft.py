"""Master aircraft catalog API router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel

from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


class AircraftRepository(BaseRepository):
    collection_name = MasterCollections.AIRCRAFT
    # Keyed by sequential `int_id`, not `_id`; no `deleted` field — hard deletes.
    soft_deletes = False


def _repo() -> AircraftRepository:
    return AircraftRepository(get_master_db())


def _ensure_int_ids(repo: AircraftRepository) -> None:
    col = repo._col
    for doc in col.find({"int_id": {"$exists": False}}):
        max_doc = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
        next_id = (max_doc["int_id"] + 1) if max_doc else 1
        col.update_one({"_id": doc["_id"]}, {"$set": {"int_id": next_id}})


def _normalize(doc: dict[str, Any]) -> dict[str, Any]:
    d = dict(doc)
    d.pop("_id", None)
    d["id"] = d.get("int_id")
    return d


@router.get("")
def list_aircraft(
    search: str = Query(""),
    status: str = Query(""),
    type_filter: str = Query(""),
) -> list[dict[str, Any]]:
    repo = _repo()
    _ensure_int_ids(repo)
    query: dict[str, Any] = {}
    if status:
        query["status"] = status
    if type_filter:
        query["type"] = type_filter
    docs = repo.find_many(query, sort=[("tail_number", 1)])
    if search.strip():
        t = search.strip().lower()
        docs = [
            d for d in docs
            if t in (d.get("tail_number") or "").lower()
            or t in (d.get("callsign") or "").lower()
            or t in (d.get("make") or "").lower()
            or t in (d.get("model") or "").lower()
            or t in (d.get("organization") or "").lower()
        ]
    return [_normalize(d) for d in docs]


@router.get("/{aircraft_id}")
def get_aircraft(aircraft_id: int) -> dict[str, Any]:
    doc = _repo().find_one({"int_id": aircraft_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    return _normalize(doc)


class AircraftBody(BaseModel):
    tail_number: str
    callsign: str = ""
    type: str = "Helicopter"
    make: str = ""
    model: str = ""
    base: str = ""
    current_location: str = ""
    status: str = "Available"
    assigned_team_id: str | None = None
    assigned_team_name: str | None = None
    organization: str | None = None
    fuel_type: str = "Jet A"
    range_nm: int = 0
    endurance_hr: float = 0.0
    cruise_kt: int = 0
    crew_min: int = 0
    crew_max: int = 0
    adsb_hex: str = ""
    radio_vhf_air: bool = False
    radio_vhf_sar: bool = False
    radio_uhf: bool = False
    cap_hoist: bool = False
    cap_nvg: bool = False
    cap_flir: bool = False
    cap_ifr: bool = False
    payload_kg: float = 0.0
    med_config: str = "None"
    serial_number: str = ""
    year: int | None = None
    owner_operator: str = ""
    registration_exp: str | None = None
    inspection_due: str | None = None
    last_100hr: str | None = None
    next_100hr: str | None = None
    notes: str = ""
    attachments: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []


@router.post("", status_code=201)
def create_aircraft(body: AircraftBody) -> dict[str, Any]:
    repo = _repo()
    _ensure_int_ids(repo)
    max_doc = repo._col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    next_id = (max_doc["int_id"] + 1) if max_doc else 1
    doc: dict[str, Any] = {
        "int_id": next_id,
        **body.model_dump(),
        "tail_number": body.tail_number.strip().upper(),
    }
    doc = repo.insert_one(doc)
    return _normalize(doc)


@router.patch("/{aircraft_id}")
def update_aircraft(
    aircraft_id: int, body: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    repo = _repo()
    existing = repo.find_one({"int_id": aircraft_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    body.pop("int_id", None)
    body.pop("_id", None)
    if "tail_number" in body and body["tail_number"]:
        body["tail_number"] = body["tail_number"].strip().upper()
    repo.update_one(existing["_id"], body)
    doc = repo.find_by_id(existing["_id"])
    return _normalize(doc)


@router.delete("/{aircraft_id}", status_code=204)
def delete_aircraft(aircraft_id: int) -> None:
    repo = _repo()
    existing = repo.find_one({"int_id": aircraft_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    repo.delete_one(existing["_id"])


class SetStatusRequest(BaseModel):
    status: str
    notes: str = ""


@router.patch("/{aircraft_id}/status")
def set_aircraft_status(aircraft_id: int, body: SetStatusRequest) -> dict[str, Any]:
    repo = _repo()
    existing = repo.find_one({"int_id": aircraft_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    update: dict[str, Any] = {"status": body.status.strip() or "Available"}
    if (body.status or "").lower() == "out of service":
        update["assigned_team_id"] = None
        update["assigned_team_name"] = None
    repo.update_one(existing["_id"], update)
    doc = repo.find_by_id(existing["_id"])
    return _normalize(doc)


class AssignTeamRequest(BaseModel):
    team_id: str | None = None
    team_name: str | None = None


@router.patch("/{aircraft_id}/assignment")
def set_aircraft_assignment(aircraft_id: int, body: AssignTeamRequest) -> dict[str, Any]:
    repo = _repo()
    existing = repo.find_one({"int_id": aircraft_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    update: dict[str, Any] = {
        "assigned_team_id": body.team_id or None,
        "assigned_team_name": body.team_name or None,
    }
    repo.update_one(existing["_id"], update)
    doc = repo.find_by_id(existing["_id"])
    return _normalize(doc)
