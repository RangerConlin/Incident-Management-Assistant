"""Weather module router.

Schema note: this replaces the old flat `weather_data` "config" blob with two
purpose-built collections — `weather_config` (locations, polling interval,
Go/No-Go thresholds) and `weather_history` (recorded readings for the trend
chart). The `weather_data` collection is kept only for the legacy
`location_codes` cache endpoints below; see
`data/db/sarapp_db/scripts/migrate_weather_module.py` for the one-time
migration of old config documents into `weather_config`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


# ---------------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------------


class WeatherDataRepository(BaseRepository):
    """Legacy collection — kept only for the location-codes cache below."""

    collection_name = IncidentCollections.WEATHER_DATA
    soft_deletes = False


class WeatherConfigRepository(BaseRepository):
    collection_name = IncidentCollections.WEATHER_CONFIG
    soft_deletes = False


class WeatherHistoryRepository(BaseRepository):
    collection_name = IncidentCollections.WEATHER_HISTORY
    soft_deletes = False


def _weather_repo(incident_id: str) -> WeatherDataRepository:
    return WeatherDataRepository(get_incident_db(incident_id))


def _config_repo(incident_id: str) -> WeatherConfigRepository:
    return WeatherConfigRepository(get_incident_db(incident_id))


def _history_repo(incident_id: str) -> WeatherHistoryRepository:
    return WeatherHistoryRepository(get_incident_db(incident_id))


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Location-codes cache (kept as-is — orthogonal to the config reshape)
# ---------------------------------------------------------------------------


class WeatherLocationCodesModel(BaseModel):
    codes: list[Dict[str, Any]] = []


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


# ---------------------------------------------------------------------------
# Go/No-Go thresholds
# ---------------------------------------------------------------------------


class GroundThresholds(BaseModel):
    wind_gust_marginal_mph: float = 20.0
    wind_gust_nogo_mph: float = 30.0
    visibility_marginal_mi: float = 3.0
    visibility_nogo_mi: float = 1.0
    ceiling_marginal_ft: float = 1500.0
    ceiling_nogo_ft: float = 500.0
    heat_index_marginal_f: float = 90.0
    heat_index_nogo_f: float = 103.0


class AviationThresholds(BaseModel):
    wind_gust_marginal_kt: float = 15.0
    wind_gust_nogo_kt: float = 25.0
    visibility_marginal_sm: float = 3.0
    visibility_nogo_sm: float = 1.0
    ceiling_marginal_ft_agl: float = 1000.0
    ceiling_nogo_ft_agl: float = 300.0
    crosswind_marginal_kt: float = 15.0
    crosswind_nogo_kt: float = 25.0


class WeatherThresholds(BaseModel):
    ground: GroundThresholds = Field(default_factory=GroundThresholds)
    aviation: AviationThresholds = Field(default_factory=AviationThresholds)


# ---------------------------------------------------------------------------
# Locations / stations
# ---------------------------------------------------------------------------


class RunwayEnd(BaseModel):
    designator: str
    heading_true_deg: float
    length_ft: Optional[float] = None


class WeatherLocation(BaseModel):
    location_id: str
    label: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    icao_codes: List[str] = Field(default_factory=list)
    is_default: bool = False
    source: str = "manual"  # "manual" | "initial_response" | "facility"
    source_ref_id: Optional[str] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None
    # Fetched once from the live runway-data API at creation time (client-side,
    # see modules/intel/weather/services/runway_api.py) and passed in here to
    # be cached — the router never calls the runway API itself.
    runway_ends: List[RunwayEnd] = Field(default_factory=list)


class WeatherLocationCreate(BaseModel):
    label: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    icao_codes: List[str] = Field(default_factory=list)
    is_default: bool = False
    source: str = "manual"  # "manual" | "initial_response" | "facility"
    source_ref_id: Optional[str] = None
    created_by: Optional[str] = None
    runway_ends: List[RunwayEnd] = Field(default_factory=list)


class WeatherConfigModel(BaseModel):
    incident_id: str
    polling_minutes: int = 10
    locations: List[WeatherLocation] = Field(default_factory=list)
    thresholds: WeatherThresholds = Field(default_factory=WeatherThresholds)
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None


class WeatherConfigUpdate(BaseModel):
    polling_minutes: Optional[int] = None
    thresholds: Optional[WeatherThresholds] = None
    updated_by: Optional[str] = None


def _default_config_doc(incident_id: str) -> Dict[str, Any]:
    return WeatherConfigModel(incident_id=incident_id).model_dump()


def _get_or_create_config(incident_id: str) -> Dict[str, Any]:
    repo = _config_repo(incident_id)
    doc = repo.find_one({"incident_id": incident_id})
    if doc is None:
        doc = repo.insert_one(_default_config_doc(incident_id))
    return doc


@router.get("/incidents/{incident_id}/weather/config")
def get_weather_config(incident_id: str) -> Dict[str, Any]:
    """Return the incident's weather configuration (locations, polling interval, thresholds)."""
    return _get_or_create_config(incident_id)


@router.put("/incidents/{incident_id}/weather/config")
def update_weather_config(incident_id: str, payload: WeatherConfigUpdate) -> Dict[str, Any]:
    """Update polling interval and/or Go/No-Go thresholds for the incident."""
    repo = _config_repo(incident_id)
    doc = _get_or_create_config(incident_id)
    updates: Dict[str, Any] = {}
    if payload.polling_minutes is not None:
        updates["polling_minutes"] = max(1, payload.polling_minutes)
    if payload.thresholds is not None:
        updates["thresholds"] = payload.thresholds.model_dump()
    if payload.updated_by is not None:
        updates["updated_by"] = payload.updated_by
    if updates:
        repo.update_one(doc["_id"], updates)
        doc = repo.find_one({"_id": doc["_id"]})
    return doc


@router.post("/incidents/{incident_id}/weather/locations")
def add_weather_location(incident_id: str, payload: WeatherLocationCreate) -> Dict[str, Any]:
    """Add a manually-entered station/location to the incident's weather config."""
    repo = _config_repo(incident_id)
    doc = _get_or_create_config(incident_id)
    location = WeatherLocation(
        location_id=uuid.uuid4().hex,
        label=payload.label,
        latitude=payload.latitude,
        longitude=payload.longitude,
        icao_codes=payload.icao_codes,
        is_default=payload.is_default,
        source=payload.source or "manual",
        source_ref_id=payload.source_ref_id,
        created_at=_utcnow_iso(),
        created_by=payload.created_by,
        runway_ends=payload.runway_ends,
    )
    locations = [WeatherLocation(**loc) for loc in doc.get("locations", [])]
    if location.is_default:
        for existing in locations:
            existing.is_default = False
    locations.append(location)
    repo.update_one(doc["_id"], {"locations": [loc.model_dump() for loc in locations]})
    return repo.find_one({"_id": doc["_id"]})


@router.delete("/incidents/{incident_id}/weather/locations/{location_id}")
def delete_weather_location(incident_id: str, location_id: str) -> Dict[str, Any]:
    """Remove a manually-added station. Auto-populated stations (source != 'manual') cannot be removed here."""
    repo = _config_repo(incident_id)
    doc = _get_or_create_config(incident_id)
    locations = [WeatherLocation(**loc) for loc in doc.get("locations", [])]
    target = next((loc for loc in locations if loc.location_id == location_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Location not found")
    if target.source != "manual":
        raise HTTPException(
            status_code=409,
            detail="This station is auto-populated from Initial Response or a facility; "
            "edit the source record instead of deleting it here.",
        )
    remaining = [loc for loc in locations if loc.location_id != location_id]
    repo.update_one(doc["_id"], {"locations": [loc.model_dump() for loc in remaining]})
    return repo.find_one({"_id": doc["_id"]})


@router.patch("/incidents/{incident_id}/weather/locations/{location_id}/default")
def set_default_weather_location(incident_id: str, location_id: str) -> Dict[str, Any]:
    """Mark one station as the default; clears is_default on all others."""
    repo = _config_repo(incident_id)
    doc = _get_or_create_config(incident_id)
    locations = [WeatherLocation(**loc) for loc in doc.get("locations", [])]
    if not any(loc.location_id == location_id for loc in locations):
        raise HTTPException(status_code=404, detail="Location not found")
    for loc in locations:
        loc.is_default = loc.location_id == location_id
    repo.update_one(doc["_id"], {"locations": [loc.model_dump() for loc in locations]})
    return repo.find_one({"_id": doc["_id"]})


# ---------------------------------------------------------------------------
# History (trend chart data)
# ---------------------------------------------------------------------------


class HistorySampleCreate(BaseModel):
    location_id: str
    recorded_at: Optional[str] = None
    temperature_f: Optional[float] = None
    wind_speed_kt: Optional[float] = None
    wind_gust_kt: Optional[float] = None
    wind_direction_deg: Optional[float] = None
    visibility_sm: Optional[float] = None
    ceiling_ft: Optional[float] = None
    relative_humidity_pct: Optional[float] = None
    barometric_pressure_hpa: Optional[float] = None
    source: str = "metar"


@router.post("/incidents/{incident_id}/weather/history")
def record_weather_history(incident_id: str, payload: HistorySampleCreate) -> Dict[str, Any]:
    """Append one poll sample to the incident's weather history (used by the trend chart)."""
    repo = _history_repo(incident_id)
    doc = payload.model_dump()
    doc["incident_id"] = incident_id
    doc["recorded_at"] = payload.recorded_at or _utcnow_iso()
    return repo.insert_one(doc)


_MAX_HISTORY_ROWS = 2000


@router.get("/incidents/{incident_id}/weather/history")
def get_weather_history(
    incident_id: str,
    location_id: str = Query(...),
    since: Optional[str] = Query(None),
    until: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Return recorded history samples for a location, optionally windowed by ISO timestamps."""
    repo = _history_repo(incident_id)
    query: Dict[str, Any] = {"incident_id": incident_id, "location_id": location_id}
    time_filter: Dict[str, Any] = {}
    if since:
        time_filter["$gte"] = since
    if until:
        time_filter["$lte"] = until
    if time_filter:
        query["recorded_at"] = time_filter
    rows = repo.find_many(query, sort=[("recorded_at", 1)], limit=_MAX_HISTORY_ROWS)
    return {"location_id": location_id, "samples": rows}
