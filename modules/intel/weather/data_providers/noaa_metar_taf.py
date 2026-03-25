"""NOAA aviation weather adapters.

The classes defined here implement the provider interfaces for METAR and TAF
using the Aviation Weather Center (ADDS) dataserver JSON endpoints.
Network calls are performed in worker threads by WeatherApiManager, so
these providers use synchronous httpx clients with timeouts.

If desired, override endpoints and tokens via
modules/intel/weather/settings/api_config.json under providers.metar/taf.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional

from .base import MetarProvider, TafProvider
from ..models.readings import MetarReading, TafReading
from ..services import settings

from datetime import datetime
from pathlib import Path

LOGGER = logging.getLogger(__name__)

# Defaults for AWC dataserver
_AWC_BASE = "https://aviationweather.gov/dataserver_current/httpparam"


class NoaaMetarProvider(MetarProvider):
    """Fetches METAR observations from the NOAA ADDS service."""

    def fetch_metar(self, icao_codes: Iterable[str]) -> List[MetarReading]:
        try:
            import httpx  # lazy import to avoid hard runtime dependency at import time
        except Exception:
            raise RuntimeError("httpx is not installed. Install with: pip install httpx")

        codes = list({code.strip().upper() for code in icao_codes if code})
        if not codes:
            LOGGER.debug("No ICAO codes supplied for METAR fetch.")
            return []
        LOGGER.info("METAR fetch requested for %s", ", ".join(codes))
        base_url, headers = _metar_endpoint_and_headers()
        params = {
            "datasource": "metars",
            "requesttype": "retrieve",
            "format": "JSON",
            "stationString": ",".join(codes),
            "hoursBeforeNow": "2",
        }
        try:
            with httpx.Client(headers=headers, timeout=httpx.Timeout(10.0)) as client:
                resp = client.get(base_url, params=params)
                resp.raise_for_status()
                payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Failed to fetch METAR: %s", exc)
            return []
        return _parse_metar(payload)


class NoaaTafProvider(TafProvider):
    """Fetches TAF bulletins from the NOAA ADDS service."""

    def fetch_taf(self, icao_codes: Iterable[str]) -> List[TafReading]:
        try:
            import httpx  # lazy import to avoid hard runtime dependency at import time
        except Exception:
            raise RuntimeError("httpx is not installed. Install with: pip install httpx")

        codes = list({code.strip().upper() for code in icao_codes if code})
        if not codes:
            LOGGER.debug("No ICAO codes supplied for TAF fetch.")
            return []
        LOGGER.info("TAF fetch requested for %s", ", ".join(codes))
        base_url, headers = _taf_endpoint_and_headers()
        params = {
            "datasource": "tafs",
            "requesttype": "retrieve",
            "format": "JSON",
            "stationString": ",".join(codes),
            "hoursBeforeNow": "12",
        }
        try:
            with httpx.Client(headers=headers, timeout=httpx.Timeout(10.0)) as client:
                resp = client.get(base_url, params=params)
                resp.raise_for_status()
                payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Failed to fetch TAF: %s", exc)
            return []
        return _parse_taf(payload)


def _metar_endpoint_and_headers() -> tuple[str, Dict[str, str]]:
    cfg = settings.load_api_config(Path("modules/intel/weather/settings/api_config.json"))
    providers: Dict[str, Any] = cfg.get("providers", {}) if isinstance(cfg, dict) else {}
    metar_cfg: Dict[str, Any] = providers.get("metar", {})
    base_url: str = (metar_cfg.get("base_url") or _AWC_BASE).rstrip("/")
    user_agent: str = (
        metar_cfg.get("user_agent")
        or "sarappdemo-weather/0.1 (+https://example.invalid; contact: admin@example.invalid)"
    )
    headers = {"User-Agent": user_agent, "Accept": "application/json"}
    return base_url, headers


def _taf_endpoint_and_headers() -> tuple[str, Dict[str, str]]:
    cfg = settings.load_api_config(Path("modules/intel/weather/settings/api_config.json"))
    providers: Dict[str, Any] = cfg.get("providers", {}) if isinstance(cfg, dict) else {}
    taf_cfg: Dict[str, Any] = providers.get("taf", {})
    base_url: str = (taf_cfg.get("base_url") or _AWC_BASE).rstrip("/")
    user_agent: str = (
        taf_cfg.get("user_agent")
        or "sarappdemo-weather/0.1 (+https://example.invalid; contact: admin@example.invalid)"
    )
    headers = {"User-Agent": user_agent, "Accept": "application/json"}
    return base_url, headers


def _parse_iso8601(dt: Optional[str]) -> Optional[datetime]:
    if not dt:
        return None
    try:
        return datetime.fromisoformat(dt.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


def _parse_metar(payload: Dict[str, Any]) -> List[MetarReading]:
    data = payload.get("response", {}).get("data", {})
    items = data.get("METAR") or []
    readings: List[MetarReading] = []
    for item in items:
        station = item.get("station_id") or item.get("icao_id") or item.get("station")
        if not station:
            continue
        readings.append(
            MetarReading(
                station=str(station).upper(),
                issued=_parse_iso8601(item.get("observation_time")),
                raw_text=item.get("raw_text", ""),
            )
        )
    return readings


def _parse_taf(payload: Dict[str, Any]) -> List[TafReading]:
    data = payload.get("response", {}).get("data", {})
    items = data.get("TAF") or []
    tafs: List[TafReading] = []
    for item in items:
        station = item.get("station_id") or item.get("icao_id") or item.get("station")
        if not station:
            continue
        tafs.append(
            TafReading(
                station=str(station).upper(),
                issued=_parse_iso8601(item.get("issue_time")),
                raw_text=item.get("raw_text", ""),
            )
        )
    return tafs


__all__ = ["NoaaMetarProvider", "NoaaTafProvider"]