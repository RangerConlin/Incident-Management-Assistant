"""Thin HTTP client wrapping the weather + notifications REST endpoints.

Isolates every raw `api_client` call the weather module needs so
`weather_manager.py` never talks to `utils.api_client` directly. Runs
client-side only — never touches Mongo, per the UI -> API -> Mongo rule.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from utils.api_client import api_client


def get_config(incident_id: str) -> Dict[str, Any]:
    return api_client.get(f"/api/incidents/{incident_id}/weather/config") or {}


def update_config(
    incident_id: str,
    *,
    polling_minutes: Optional[int] = None,
    thresholds: Optional[Dict[str, Any]] = None,
    updated_by: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if polling_minutes is not None:
        payload["polling_minutes"] = polling_minutes
    if thresholds is not None:
        payload["thresholds"] = thresholds
    if updated_by is not None:
        payload["updated_by"] = updated_by
    return api_client.put(f"/api/incidents/{incident_id}/weather/config", json=payload) or {}


def add_location(
    incident_id: str,
    *,
    label: str,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    icao_codes: Optional[List[str]] = None,
    is_default: bool = False,
    source: str = "manual",
    source_ref_id: Optional[str] = None,
    created_by: Optional[str] = None,
    runway_ends: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    payload = {
        "label": label,
        "latitude": latitude,
        "longitude": longitude,
        "icao_codes": icao_codes or [],
        "is_default": is_default,
        "source": source,
        "source_ref_id": source_ref_id,
        "runway_ends": runway_ends or [],
        "created_by": created_by,
    }
    return api_client.post(f"/api/incidents/{incident_id}/weather/locations", json=payload) or {}


def delete_location(incident_id: str, location_id: str) -> Dict[str, Any]:
    return api_client.delete(f"/api/incidents/{incident_id}/weather/locations/{location_id}") or {}


def set_default_location(incident_id: str, location_id: str) -> Dict[str, Any]:
    return api_client.patch(f"/api/incidents/{incident_id}/weather/locations/{location_id}/default") or {}


def record_history(incident_id: str, sample: Dict[str, Any]) -> Dict[str, Any]:
    return api_client.post(f"/api/incidents/{incident_id}/weather/history", json=sample) or {}


def get_history(
    incident_id: str,
    location_id: str,
    *,
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {"location_id": location_id}
    if since:
        params["since"] = since
    if until:
        params["until"] = until
    return api_client.get(f"/api/incidents/{incident_id}/weather/history", params=params) or {}


def get_location_codes(incident_id: str) -> Dict[str, Any]:
    return api_client.get(f"/api/incidents/{incident_id}/weather/location-codes") or {}


def update_location_codes(incident_id: str, codes: List[Dict[str, Any]]) -> Dict[str, Any]:
    return api_client.post(
        f"/api/incidents/{incident_id}/weather/location-codes", json={"codes": codes}
    ) or {}


# -- Alerts (routed through the shared notifications system, source_type="weather_alert") --


def emit_weather_alert(
    incident_id: str,
    *,
    title: str,
    message: str,
    source_id: str,
    severity: str = "routine",
) -> Dict[str, Any]:
    payload = {
        "title": title,
        "message": message,
        "source_type": "weather_alert",
        "source_id": source_id,
        "severity": severity,
        "category": "weather",
        "requires_acknowledgement": True,
    }
    return api_client.post(f"/api/incidents/{incident_id}/notifications", json=payload) or {}


def list_weather_alerts(incident_id: str) -> List[Dict[str, Any]]:
    return api_client.get(
        f"/api/incidents/{incident_id}/notifications",
        params={"source_type": "weather_alert"},
    ) or []


def acknowledge_weather_alert(incident_id: str, notification_id: int, *, acknowledged_by: str) -> Dict[str, Any]:
    return api_client.post(
        f"/api/incidents/{incident_id}/notifications/{notification_id}/acknowledge",
        json={"acknowledged_by": acknowledged_by},
    ) or {}


# -- Aviation/facility/initial-response auto-population sources --


def list_airport_facilities(incident_id: str) -> List[Dict[str, Any]]:
    airports = api_client.get(
        f"/api/incidents/{incident_id}/facilities", params={"facility_type": "airport"}
    ) or []
    helibases = api_client.get(
        f"/api/incidents/{incident_id}/facilities", params={"facility_type": "helibase"}
    ) or []
    return list(airports) + list(helibases)


def get_initial_response_aircraft_info(incident_id: str) -> Dict[str, Any]:
    doc = api_client.get(f"/api/incidents/{incident_id}/initialresponse/overview") or {}
    if str(doc.get("incident_mode") or "") != "Missing Aircraft":
        return {}
    return dict(doc.get("aircraft_info") or {})


__all__ = [
    "get_config",
    "update_config",
    "add_location",
    "delete_location",
    "set_default_location",
    "record_history",
    "get_history",
    "get_location_codes",
    "update_location_codes",
    "emit_weather_alert",
    "list_weather_alerts",
    "acknowledge_weather_alert",
    "list_airport_facilities",
    "get_initial_response_aircraft_info",
]
