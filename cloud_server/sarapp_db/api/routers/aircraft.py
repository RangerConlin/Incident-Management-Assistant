"""Master aircraft catalog API router."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel

from sarapp_db.mongo.mongo_client import get_client
from sarapp_db.mongo.database_manager import DB_MASTER
from sarapp_db.mongo.collection_names import MasterCollections

router = APIRouter()


def _col():
    return get_client()[DB_MASTER][MasterCollections.AIRCRAFT]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_int_ids(col) -> None:
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
    col = _col()
    _ensure_int_ids(col)
    query: dict[str, Any] = {}
    if status:
        query["status"] = status
    if type_filter:
        query["type"] = type_filter
    docs = list(col.find(query).sort("tail_number", 1))
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
    doc = _col().find_one({"int_id": aircraft_id})
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
    col = _col()
    _ensure_int_ids(col)
    max_doc = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    next_id = (max_doc["int_id"] + 1) if max_doc else 1
    now = _utcnow()
    doc: dict[str, Any] = {
        "int_id": next_id,
        **body.model_dump(),
        "tail_number": body.tail_number.strip().upper(),
        "created_at": now,
        "updated_at": now,
    }
    col.insert_one(doc)
    doc.pop("_id", None)
    return _normalize(doc)


@router.patch("/{aircraft_id}")
def update_aircraft(
    aircraft_id: int, body: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    col = _col()
    existing = col.find_one({"int_id": aircraft_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    body.pop("int_id", None)
    body.pop("_id", None)
    body["updated_at"] = _utcnow()
    if "tail_number" in body and body["tail_number"]:
        body["tail_number"] = body["tail_number"].strip().upper()
    col.update_one({"int_id": aircraft_id}, {"$set": body})
    doc = col.find_one({"int_id": aircraft_id})
    return _normalize(doc)


@router.delete("/{aircraft_id}", status_code=204)
def delete_aircraft(aircraft_id: int) -> None:
    result = _col().delete_one({"int_id": aircraft_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Aircraft not found")


class SetStatusRequest(BaseModel):
    status: str
    notes: str = ""


@router.patch("/{aircraft_id}/status")
def set_aircraft_status(aircraft_id: int, body: SetStatusRequest) -> dict[str, Any]:
    col = _col()
    update: dict[str, Any] = {"status": body.status.strip() or "Available", "updated_at": _utcnow()}
    if (body.status or "").lower() == "out of service":
        update["assigned_team_id"] = None
        update["assigned_team_name"] = None
    result = col.update_one({"int_id": aircraft_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    doc = col.find_one({"int_id": aircraft_id})
    return _normalize(doc)


class AssignTeamRequest(BaseModel):
    team_id: str | None = None
    team_name: str | None = None


@router.patch("/{aircraft_id}/assignment")
def set_aircraft_assignment(aircraft_id: int, body: AssignTeamRequest) -> dict[str, Any]:
    col = _col()
    update: dict[str, Any] = {
        "assigned_team_id": body.team_id or None,
        "assigned_team_name": body.team_name or None,
        "updated_at": _utcnow(),
    }
    result = col.update_one({"int_id": aircraft_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    doc = col.find_one({"int_id": aircraft_id})
    return _normalize(doc)
