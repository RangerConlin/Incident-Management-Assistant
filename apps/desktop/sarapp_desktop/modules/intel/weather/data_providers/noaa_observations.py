"""NOAA/NWS current-observation provider for point-based weather locations."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .base import get_shared_client
from .nws_points import NwsPointsProvider
from ..models.readings import MetarReading
from ..services import settings

LOGGER = logging.getLogger(__name__)

_NWS_API_URL = "https://api.weather.gov"


class NoaaObservationProvider:
    """Fetch the latest NWS observation near a latitude/longitude point."""

    def __init__(self, points_provider: Optional[NwsPointsProvider] = None) -> None:
        self._points_provider = points_provider or NwsPointsProvider()

    def fetch_current_observation(self, latitude: float, longitude: float) -> Optional[MetarReading]:
        point = self._points_provider.resolve(latitude, longitude) or {}
        stations = [str(station).strip().upper() for station in point.get("stations") or [] if station]
        if not stations:
            return None

        base_url, headers = _observations_endpoint_and_headers()
        client = get_shared_client()
        for station in stations:
            try:
                resp = client.get(f"{base_url}/stations/{station}/observations/latest", headers=headers)
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                payload = resp.json() or {}
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Failed to fetch latest NWS observation for %s: %s", station, exc)
                continue
            reading = _parse_observation(station, payload)
            if reading is not None:
                return reading
        return None


def _observations_endpoint_and_headers() -> tuple[str, Dict[str, str]]:
    cfg = settings.load_api_config(Path("modules/intel/weather/settings/api_config.json"))
    providers: Dict[str, Any] = cfg.get("providers", {}) if isinstance(cfg, dict) else {}
    obs_cfg: Dict[str, Any] = providers.get("observations", {})
    base_url: str = (obs_cfg.get("base_url") or _NWS_API_URL).rstrip("/")
    user_agent: str = (
        obs_cfg.get("user_agent")
        or "IncidentManagementAssistant/1.0 (contact: admin@example.invalid)"
    )
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/geo+json, application/json;q=0.9",
    }
    return base_url, headers


def _parse_observation(station: str, payload: Dict[str, Any]) -> Optional[MetarReading]:
    props = payload.get("properties") if isinstance(payload, dict) else None
    if not isinstance(props, dict):
        return None

    decoded = {
        "source": "nws_observation",
        "temp": _quantity_value(props.get("temperature")),
        "dewp": _quantity_value(props.get("dewpoint")),
        "wspd": _meters_per_second_to_knots(_quantity_value(props.get("windSpeed"))),
        "wgst": _meters_per_second_to_knots(_quantity_value(props.get("windGust"))),
        "wdir": _quantity_value(props.get("windDirection")),
        "visib": _meters_to_statute_miles(_quantity_value(props.get("visibility"))),
        "altim": _pascals_to_hpa(_quantity_value(props.get("barometricPressure"))),
        "relative_humidity_pct": _quantity_value(props.get("relativeHumidity")),
        "clouds": _cloud_layers(props.get("cloudLayers")),
    }
    return MetarReading(
        station=station,
        issued=_parse_iso8601(props.get("timestamp")),
        raw_text=str(props.get("rawMessage") or ""),
        decoded=decoded,
    )


def _quantity_value(value: Any) -> Optional[float]:
    if isinstance(value, dict):
        value = value.get("value")
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _meters_per_second_to_knots(value: Optional[float]) -> Optional[float]:
    return value * 1.943844 if isinstance(value, (int, float)) else None


def _meters_to_statute_miles(value: Optional[float]) -> Optional[float]:
    return value / 1609.344 if isinstance(value, (int, float)) else None


def _meters_to_feet(value: Optional[float]) -> Optional[float]:
    return value * 3.28084 if isinstance(value, (int, float)) else None


def _pascals_to_hpa(value: Optional[float]) -> Optional[float]:
    return value / 100.0 if isinstance(value, (int, float)) else None


def _cloud_layers(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    layers: list[dict[str, Any]] = []
    for layer in value:
        if not isinstance(layer, dict):
            continue
        layers.append(
            {
                "cover": str(layer.get("amount") or "").upper(),
                "base": _meters_to_feet(_quantity_value(layer.get("base"))),
            }
        )
    return layers


def _parse_iso8601(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


__all__ = ["NoaaObservationProvider"]
