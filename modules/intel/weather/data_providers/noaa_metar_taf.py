"""NOAA aviation weather adapters.

Updated to use the Aviation Weather Center (AWC) /api/data endpoints
for METAR and TAF in JSON format.

If desired, override endpoints and tokens via
modules/intel/weather/settings/api_config.json under providers.metar/taf.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional

from .base import MetarProvider, TafProvider
from ..models.readings import MetarReading, TafReading
from ..services import settings
from ..services import cache as weather_cache

from datetime import datetime
from pathlib import Path

LOGGER = logging.getLogger(__name__)

# Defaults for AWC /api/data endpoints
_AWC_METAR_URL = "https://aviationweather.gov/api/data/metar"
_AWC_TAF_URL = "https://aviationweather.gov/api/data/taf"


class NoaaMetarProvider(MetarProvider):
    """Fetches METAR observations from the NOAA AWC API."""

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
            "ids": ",".join(codes),
            "format": "json",
        }
        try:
            with httpx.Client(headers=headers, timeout=httpx.Timeout(10.0)) as client:
                resp = client.get(base_url, params=params)
                if resp.status_code == 204:
                    return []
                if resp.status_code != 200:
                    LOGGER.warning("METAR fetch HTTP %s for %s", resp.status_code, resp.url)
                    return []
                payload = resp.json()
                try:
                    weather_cache.write_cache("debug_awc_metar_raw", {"url": str(resp.url), "payload": payload})
                except Exception:
                    pass
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Failed to fetch METAR: %s", exc)
            return []
        return _parse_metar(payload)


class NoaaTafProvider(TafProvider):
    """Fetches TAF bulletins from the NOAA AWC API."""

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
            "ids": ",".join(codes),
            "format": "json",
        }
        try:
            with httpx.Client(headers=headers, timeout=httpx.Timeout(10.0)) as client:
                resp = client.get(base_url, params=params)
                if resp.status_code == 204:
                    return []
                if resp.status_code != 200:
                    LOGGER.warning("TAF fetch HTTP %s for %s", resp.status_code, resp.url)
                    return []
                payload = resp.json()
                try:
                    weather_cache.write_cache("debug_awc_taf_raw", {"url": str(resp.url), "payload": payload})
                except Exception:
                    pass
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Failed to fetch TAF: %s", exc)
            return []
        return _parse_taf(payload)


def _metar_endpoint_and_headers() -> tuple[str, Dict[str, str]]:
    cfg = settings.load_api_config(Path("modules/intel/weather/settings/api_config.json"))
    providers: Dict[str, Any] = cfg.get("providers", {}) if isinstance(cfg, dict) else {}
    metar_cfg: Dict[str, Any] = providers.get("metar", {})
    base_url: str = (metar_cfg.get("base_url") or _AWC_METAR_URL).rstrip("/")
    user_agent: Optional[str] = metar_cfg.get("user_agent") or None
    if "aviationweather.gov" in base_url and ("/adds/" in base_url or "/dataserver" in base_url):
        LOGGER.warning(
            "Configured AWC METAR endpoint appears legacy; prefer /api/data/metar: %s",
            base_url,
        )
    headers: Dict[str, str] = {"Accept": "application/json"}
    if user_agent:
        headers["User-Agent"] = user_agent
    return base_url, headers


def _taf_endpoint_and_headers() -> tuple[str, Dict[str, str]]:
    cfg = settings.load_api_config(Path("modules/intel/weather/settings/api_config.json"))
    providers: Dict[str, Any] = cfg.get("providers", {}) if isinstance(cfg, dict) else {}
    taf_cfg: Dict[str, Any] = providers.get("taf", {})
    base_url: str = (taf_cfg.get("base_url") or _AWC_TAF_URL).rstrip("/")
    user_agent: Optional[str] = taf_cfg.get("user_agent") or None
    if "aviationweather.gov" in base_url and ("/adds/" in base_url or "/dataserver" in base_url):
        LOGGER.warning(
            "Configured AWC TAF endpoint appears legacy; prefer /api/data/taf: %s",
            base_url,
        )
    headers: Dict[str, str] = {"Accept": "application/json"}
    if user_agent:
        headers["User-Agent"] = user_agent
    return base_url, headers


def _parse_iso8601(dt: Optional[str]) -> Optional[datetime]:
    if not dt:
        return None
    try:
        return datetime.fromisoformat(dt.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


def _first(payload: Dict[str, Any], *keys: str) -> Optional[Any]:
    for k in keys:
        if k in payload and payload[k] is not None:
            return payload[k]
    return None


def _iter_items(payload: Any, item_key_options: List[str]) -> List[Dict[str, Any]]:
    """Return a list of item dicts from payload handling several shapes:
    - Direct list of dicts
    - Dict with a single array value under one of item_key_options
    - Dict with "data" containing list
    """
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for k in ["data", *item_key_options]:
            v = payload.get(k)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
    return []


def _parse_metar(payload: Dict[str, Any]) -> List[MetarReading]:
    items = _iter_items(payload, ["METAR", "metars", "metar"])
    readings: List[MetarReading] = []
    for item in items:
        station = _first(
            item,
            "icaoId",
            "icao",
            "station",
            "stationId",
            "station_id",
        )
        if not station:
            continue
        issued = _first(item, "obsTime", "observation_time", "observationTime")
        raw = _first(item, "rawOb", "raw_text", "rawText", "raw") or ""
        readings.append(
            MetarReading(
                station=str(station).upper(),
                issued=_parse_iso8601(issued if isinstance(issued, str) else None),
                raw_text=str(raw),
                decoded=item,
            )
        )
    return readings


def _parse_taf(payload: Dict[str, Any]) -> List[TafReading]:
    items = _iter_items(payload, ["TAF", "tafs", "taf"])
    tafs: List[TafReading] = []
    for item in items:
        station = _first(
            item,
            "icaoId",
            "icao",
            "station",
            "stationId",
            "station_id",
        )
        if not station:
            continue
        issued = _first(item, "issueTime", "issue_time")
        raw = _first(item, "rawTAF", "raw_text", "rawText", "raw") or ""
        tafs.append(
            TafReading(
                station=str(station).upper(),
                issued=_parse_iso8601(issued if isinstance(issued, str) else None),
                raw_text=str(raw),
            )
        )
    return tafs


__all__ = ["NoaaMetarProvider", "NoaaTafProvider"]
