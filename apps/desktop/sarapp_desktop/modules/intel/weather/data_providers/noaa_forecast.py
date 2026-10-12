"""NOAA point forecast provider."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import ForecastProvider, get_shared_client
from ..models.readings import ForecastPeriod
from ..services import settings

LOGGER = logging.getLogger(__name__)

_NWS_POINTS_URL = "https://api.weather.gov/points"


class NoaaForecastProvider(ForecastProvider):
    """Fetch a short point forecast from the NWS API."""

    def fetch_forecast(
        self,
        latitude: float,
        longitude: float,
        forecast_url: str | None = None,
    ) -> List[ForecastPeriod]:
        points_url, headers = _forecast_endpoint_and_headers()
        try:
            client = get_shared_client()
            if not forecast_url:
                points_resp = client.get(
                    f"{points_url}/{latitude:.4f},{longitude:.4f}",
                    headers=headers,
                )
                points_resp.raise_for_status()
                points_payload = points_resp.json()
                properties = points_payload.get("properties") or {}
                forecast_url = properties.get("forecast") or properties.get("forecastHourly")
            if not forecast_url:
                return []
            forecast_resp = client.get(forecast_url, headers=headers)
            forecast_resp.raise_for_status()
            forecast_payload = forecast_resp.json()
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Failed to fetch forecast: %s", exc)
            return []

        periods = (forecast_payload.get("properties") or {}).get("periods") or []
        return [_parse_period(item) for item in periods if isinstance(item, dict)]


def _forecast_endpoint_and_headers() -> tuple[str, Dict[str, str]]:
    cfg = settings.load_api_config(Path("modules/intel/weather/settings/api_config.json"))
    providers: Dict[str, Any] = cfg.get("providers", {}) if isinstance(cfg, dict) else {}
    forecast_cfg: Dict[str, Any] = providers.get("forecast", {})
    base_url: str = (forecast_cfg.get("base_url") or _NWS_POINTS_URL).rstrip("/")
    user_agent: str = (
        forecast_cfg.get("user_agent")
        or "IncidentManagementAssistant/1.0 (contact: admin@example.invalid)"
    )
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/geo+json, application/json;q=0.9",
    }
    return base_url, headers


def _parse_iso8601(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


def _parse_period(item: Dict[str, Any]) -> ForecastPeriod:
    return ForecastPeriod(
        name=str(item.get("name") or "Forecast"),
        start_time=_parse_iso8601(item.get("startTime")),
        end_time=_parse_iso8601(item.get("endTime")),
        temperature=item.get("temperature"),
        wind_speed=item.get("windSpeed"),
        detailed_text=item.get("detailedForecast") or item.get("shortForecast"),
    )


__all__ = ["NoaaForecastProvider"]
