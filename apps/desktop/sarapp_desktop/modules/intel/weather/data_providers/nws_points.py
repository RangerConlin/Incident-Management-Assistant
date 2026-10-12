"""NWS points metadata provider.

Resolves a coordinate to the NWS location codes needed by other queries:
forecast office (CWA), gridpoint, forecast URLs, and nearby observation
stations. Endpoints may be overridden via
modules/intel/weather/settings/api_config.json under providers.points.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import get_shared_client
from ..services import settings

LOGGER = logging.getLogger(__name__)

_NWS_POINTS_URL = "https://api.weather.gov/points"


class NwsPointsProvider:
    """Fetch NWS location metadata for a coordinate."""

    def resolve(self, latitude: float, longitude: float) -> Dict[str, Any] | None:
        points_url, headers = _points_endpoint_and_headers()
        try:
            client = get_shared_client()
            resp = client.get(
                f"{points_url}/{latitude:.4f},{longitude:.4f}",
                headers=headers,
            )
            resp.raise_for_status()
            props = (resp.json() or {}).get("properties") or {}
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning(
                "Failed to resolve NWS point for %.4f,%.4f: %s", latitude, longitude, exc
            )
            return None

        office = str(props.get("cwa") or "").strip().upper()
        if not office:
            office_url = str(props.get("forecastOffice") or "")
            office = office_url.rsplit("/", 1)[-1].strip().upper() if office_url else ""

        entry: Dict[str, Any] = {
            "office": office,
            "grid_id": str(props.get("gridId") or office),
            "grid_x": props.get("gridX"),
            "grid_y": props.get("gridY"),
            "forecast_url": str(props.get("forecast") or ""),
            "forecast_hourly_url": str(props.get("forecastHourly") or ""),
            "time_zone": str(props.get("timeZone") or ""),
            "stations": self._nearby_stations(
                client, props.get("observationStations"), headers
            ),
        }
        if not entry["office"] and not entry["forecast_url"]:
            return None
        return entry

    @staticmethod
    def _nearby_stations(
        client,
        stations_url: Optional[str],
        headers: Dict[str, str],
        limit: int = 5,
    ) -> List[str]:
        if not stations_url:
            return []
        try:
            resp = client.get(str(stations_url), headers=headers)
            resp.raise_for_status()
            features = (resp.json() or {}).get("features") or []
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Failed to fetch nearby observation stations: %s", exc)
            return []
        stations: List[str] = []
        for feature in features[:limit]:
            sid = ((feature or {}).get("properties") or {}).get("stationIdentifier")
            if sid:
                stations.append(str(sid).upper())
        return stations


def _points_endpoint_and_headers() -> tuple[str, Dict[str, str]]:
    cfg = settings.load_api_config(Path("modules/intel/weather/settings/api_config.json"))
    providers: Dict[str, Any] = cfg.get("providers", {}) if isinstance(cfg, dict) else {}
    points_cfg: Dict[str, Any] = providers.get("points", {})
    base_url: str = (points_cfg.get("base_url") or _NWS_POINTS_URL).rstrip("/")
    user_agent: str = (
        points_cfg.get("user_agent")
        or "IncidentManagementAssistant/1.0 (contact: admin@example.invalid)"
    )
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/geo+json, application/json;q=0.9",
    }
    return base_url, headers


__all__ = ["NwsPointsProvider"]
