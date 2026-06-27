"""NOAA NWS advisories data provider.

Implements the :class:`AdvisoryProvider` interface by calling the public
National Weather Service API (api.weather.gov). Network calls are performed
in worker threads by :class:`WeatherApiManager`, so this provider uses a
simple synchronous ``httpx`` client with reasonable timeouts.

Notes
-----
- The NWS API requires a descriptive ``User-Agent`` with contact info.
  Configure this via ``modules/intel/weather/settings/api_config.json`` as
  ``providers.advisories.user_agent``. A conservative default is used if
  not provided.
- This implementation only parses the subset of fields required by our
  UI and data model (see ``Advisory``).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import AdvisoryProvider, get_shared_client
from ..models.advisory import Advisory
from ..services import settings

from datetime import datetime
from pathlib import Path

LOGGER = logging.getLogger(__name__)


class NoaaNwsAdvisoryProvider(AdvisoryProvider):
    """Fetches weather advisories for a location from the NWS API."""

    def fetch_advisories(self, latitude: float, longitude: float) -> List[Advisory]:
        LOGGER.info(
            "Advisory fetch requested for lat=%s lon=%s", latitude, longitude
        )
        base_url, headers = _advisory_endpoint_and_headers()
        url = f"{base_url}/alerts/active"
        params = {"point": f"{latitude:.4f},{longitude:.4f}"}
        try:
            client = get_shared_client()
            resp = client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Failed to fetch advisories: %s", exc)
            return []

        return _parse_nws_alerts(payload)


def _advisory_endpoint_and_headers() -> tuple[str, Dict[str, str]]:
    """Return base URL and headers derived from api_config.json.

    Defaults to the official NWS API host and a conservative User-Agent if
    config entries are missing.
    """

    cfg = settings.load_api_config(
        Path("modules/intel/weather/settings/api_config.json")
    )
    providers: Dict[str, Any] = cfg.get("providers", {}) if isinstance(cfg, dict) else {}
    adv_cfg: Dict[str, Any] = providers.get("advisories", {})
    base_url: str = (adv_cfg.get("base_url") or "https://api.weather.gov").rstrip("/")
    user_agent: str = (
        adv_cfg.get("user_agent")
        or "sarappdemo-weather/0.1 (+https://example.invalid; contact: admin@example.invalid)"
    )
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/geo+json, application/json;q=0.9",
    }
    return base_url, headers


def _parse_iso8601(dt: Optional[str]) -> Optional[datetime]:
    if not dt:
        return None
    try:
        # NWS uses Z suffix; replace for fromisoformat
        return datetime.fromisoformat(dt.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


def _parse_nws_alerts(payload: Dict[str, Any]) -> List[Advisory]:
    """Map NWS alerts GeoJSON into our Advisory list."""

    features = payload.get("features") or []
    advisories: List[Advisory] = []
    for feat in features:
        props = feat.get("properties", {})
        advisories.append(
            Advisory(
                event=props.get("event", "Advisory"),
                severity=props.get("severity"),
                start=_parse_iso8601(props.get("effective") or props.get("onset")),
                end=_parse_iso8601(props.get("ends") or props.get("expires")),
                headline=props.get("headline"),
                description=props.get("description"),
                certainty=props.get("certainty"),
                urgency=props.get("urgency"),
                affected_areas=(props.get("areaDesc") or "").split("; ") if props.get("areaDesc") else None,
            )
        )
    return advisories


__all__ = ["NoaaNwsAdvisoryProvider"]
