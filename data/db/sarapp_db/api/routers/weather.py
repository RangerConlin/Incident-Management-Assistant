from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


class WeatherDataRepository(BaseRepository):
    collection_name = IncidentCollections.WEATHER_DATA
    soft_deletes = False


def _weather_repo(incident_id: str) -> WeatherDataRepository:
    return WeatherDataRepository(get_incident_db(incident_id))


class WeatherLocationCodesModel(BaseModel):
    codes: list[Dict[str, Any]] = []


class WeatherSettingsModel(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_nm: Optional[float] = 25.0
    icao_codes: Optional[list[str]] = None
    polling_minutes: Optional[int] = 10
    active_location_preset: Optional[str] = None
    location_presets: Optional[list[Dict[str, Any]]] = None
    weather_payload: Optional[Dict[str, Any]] = None


@router.get("/incidents/{incident_id}/weather/location-codes")
def get_weather_location_codes(incident_id: str) -> Dict[str, Any]:
    """Return resolved NWS location codes (office/grid/stations) for the incident."""
    repo = _weather_repo(incident_id)
    doc = repo.find_one({"incident_id": incident_id, "key": "location_codes"})
    codes = (doc or {}).get("codes") or []
    return {"codes": [item for item in codes if isinstance(item, dict)]}


@router.post("/incidents/{incident_id}/weather/location-codes")
def update_weather_location_codes(
    incident_id: str, payload: WeatherLocationCodesModel
) -> Dict[str, Any]:
    """Persist resolved NWS location codes for the incident."""
    repo = _weather_repo(incident_id)
    doc = repo.find_one({"incident_id": incident_id, "key": "location_codes"})
    update_data = {
        "incident_id": incident_id,
        "key": "location_codes",
        "codes": payload.codes,
    }
    if doc:
        repo.update_one(doc["_id"], update_data)
        updated = repo.find_one({"_id": doc["_id"]})
    else:
        updated = repo.insert_one(update_data)
    return {"codes": (updated or {}).get("codes") or []}


@router.get("/incidents/{incident_id}/weather")
def get_incident_weather(incident_id: str) -> Dict[str, Any]:
    """Retrieve weather configuration and cached readings for the incident."""
    repo = _weather_repo(incident_id)
    doc = repo.find_one({"incident_id": incident_id, "key": "config"})
    if not doc:
        return {
            "incident_id": incident_id,
            "key": "config",
            "latitude": 39.8283,
            "longitude": -98.5795,
            "radius_nm": 25.0,
            "icao_codes": [],
            "polling_minutes": 10,
            "active_location_preset": "",
            "location_presets": [],
            "weather_payload": {},
        }
    return doc


@router.post("/incidents/{incident_id}/weather")
def update_incident_weather(incident_id: str, settings: WeatherSettingsModel) -> Dict[str, Any]:
    """Save or update weather settings for the incident."""
    repo = _weather_repo(incident_id)
    doc = repo.find_one({"incident_id": incident_id, "key": "config"})
    
    update_data = {
        "incident_id": incident_id,
        "key": "config",
        "latitude": settings.latitude,
        "longitude": settings.longitude,
        "radius_nm": settings.radius_nm,
        "icao_codes": settings.icao_codes or [],
        "polling_minutes": settings.polling_minutes,
        "active_location_preset": settings.active_location_preset or "",
        "location_presets": settings.location_presets or [],
    }
    
    if settings.weather_payload is not None:
        update_data["weather_payload"] = settings.weather_payload
    elif doc and "weather_payload" in doc:
        update_data["weather_payload"] = doc["weather_payload"]
    else:
        update_data["weather_payload"] = {}

    if doc:
        repo.update_one(doc["_id"], update_data)
        updated = repo.find_one({"_id": doc["_id"]})
    else:
        updated = repo.insert_one(update_data)
        
    return updated
