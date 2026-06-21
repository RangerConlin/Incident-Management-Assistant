from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class GeocodeResult:
    address: str
    latitude: float
    longitude: float


def _load_config() -> dict:
    cfg_path = Path("settings/geocoding_config.json")
    if cfg_path.exists():
        try:
            return json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def geocode_address(address: str) -> Optional[GeocodeResult]:
    """Geocode an address using a configurable provider with sensible fallbacks.

    Provider selection (in settings/geocoding_config.json):
      {"provider": "nominatim"|"census"|"opencage", "user_agent": "...", "api_key": "..."}

    Default behavior: try Nominatim; if blocked (e.g., 403) or fails, fall back to
    US Census Geocoder for US addresses. Returns None on failure.
    """

    addr = address.strip()
    if not addr:
        return None

    cfg = _load_config()
    # Default to Census to avoid Nominatim entirely for now
    provider = str(cfg.get("provider") or "").lower().strip() or "census"

    # First choice according to config
    if provider == "nominatim":
        res = _geocode_nominatim(addr, cfg)
        if res is not None:
            return res
        # Fallback
        return _geocode_census(addr)
    if provider == "census":
        return _geocode_census(addr)
    if provider == "opencage":
        res = _geocode_opencage(addr, cfg)
        if res is not None:
            return res
        # Fallback
        return _geocode_census(addr)
    # Unknown provider: use Census only
    return _geocode_census(addr)


def _geocode_nominatim(addr: str, cfg: dict) -> Optional[GeocodeResult]:
    try:
        import httpx
    except Exception:
        raise RuntimeError("httpx is not installed. Install with: pip install httpx")

    base_url = cfg.get("base_url") or "https://nominatim.openstreetmap.org/search"
    user_agent = (
        cfg.get("user_agent")
        or "IncidentMgmtAssistant/0.1 (set user_agent in settings/geocoding_config.json with contact)"
    )
    params = {"q": addr, "format": "jsonv2", "limit": 1, "addressdetails": 1}
    try:
        with httpx.Client(headers={"User-Agent": user_agent}, timeout=httpx.Timeout(8.0)) as client:
            resp = client.get(base_url, params=params)
            if resp.status_code != 200:
                return None
            items = resp.json()
    except Exception:
        return None
    if not items:
        return None
    item = items[0]
    try:
        lat = float(item.get("lat"))
        lon = float(item.get("lon"))
    except Exception:
        return None
    disp = item.get("display_name") or addr
    return GeocodeResult(address=str(disp), latitude=lat, longitude=lon)


def _geocode_census(addr: str) -> Optional[GeocodeResult]:
    """US Census Geocoder (best-effort, US-only)."""
    try:
        import httpx
    except Exception:
        raise RuntimeError("httpx is not installed. Install with: pip install httpx")

    base_url = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
    params = {"address": addr, "benchmark": "2020", "format": "json"}
    try:
        with httpx.Client(timeout=httpx.Timeout(8.0)) as client:
            resp = client.get(base_url, params=params)
            if resp.status_code != 200:
                return None
            data = resp.json()
    except Exception:
        return None
    matches = (
        data.get("result", {}).get("addressMatches") if isinstance(data, dict) else None
    )
    if not matches:
        return None
    item = matches[0]
    coords = item.get("coordinates") or {}
    try:
        lon = float(coords.get("x"))
        lat = float(coords.get("y"))
    except Exception:
        return None
    disp = item.get("matchedAddress") or addr
    return GeocodeResult(address=str(disp), latitude=lat, longitude=lon)


def _geocode_opencage(addr: str, cfg: dict) -> Optional[GeocodeResult]:
    key = cfg.get("api_key")
    if not key:
        return None
    try:
        import httpx
    except Exception:
        raise RuntimeError("httpx is not installed. Install with: pip install httpx")
    base_url = "https://api.opencagedata.com/geocode/v1/json"
    params = {"q": addr, "key": key, "limit": 1}
    try:
        with httpx.Client(timeout=httpx.Timeout(8.0)) as client:
            resp = client.get(base_url, params=params)
            if resp.status_code != 200:
                return None
            data = resp.json()
    except Exception:
        return None
    results = data.get("results") or []
    if not results:
        return None
    r0 = results[0]
    geom = r0.get("geometry") or {}
    try:
        lat = float(geom.get("lat"))
        lon = float(geom.get("lng"))
    except Exception:
        return None
    disp = r0.get("formatted") or addr
    return GeocodeResult(address=str(disp), latitude=lat, longitude=lon)


def reverse_geocode_coordinates(latitude: float, longitude: float) -> Optional[GeocodeResult]:
    cfg = _load_config()
    provider = str(cfg.get("provider") or "").lower().strip() or "census"
    if provider == "opencage":
        result = _reverse_geocode_opencage(latitude, longitude, cfg)
        if result is not None:
            return result
    return _reverse_geocode_nominatim(latitude, longitude, cfg)


def _reverse_geocode_nominatim(latitude: float, longitude: float, cfg: dict) -> Optional[GeocodeResult]:
    try:
        import httpx
    except Exception:
        raise RuntimeError("httpx is not installed. Install with: pip install httpx")

    base_url = cfg.get("reverse_base_url") or "https://nominatim.openstreetmap.org/reverse"
    user_agent = (
        cfg.get("user_agent")
        or "IncidentMgmtAssistant/0.1 (set user_agent in settings/geocoding_config.json with contact)"
    )
    params = {"lat": latitude, "lon": longitude, "format": "jsonv2"}
    try:
        with httpx.Client(headers={"User-Agent": user_agent}, timeout=httpx.Timeout(8.0)) as client:
            resp = client.get(base_url, params=params)
            if resp.status_code != 200:
                return None
            data = resp.json()
    except Exception:
        return None
    disp = data.get("display_name") if isinstance(data, dict) else None
    if not disp:
        return None
    return GeocodeResult(address=str(disp), latitude=float(latitude), longitude=float(longitude))


def _reverse_geocode_opencage(latitude: float, longitude: float, cfg: dict) -> Optional[GeocodeResult]:
    key = cfg.get("api_key")
    if not key:
        return None
    try:
        import httpx
    except Exception:
        raise RuntimeError("httpx is not installed. Install with: pip install httpx")
    base_url = "https://api.opencagedata.com/geocode/v1/json"
    params = {"q": f"{latitude},{longitude}", "key": key, "limit": 1}
    try:
        with httpx.Client(timeout=httpx.Timeout(8.0)) as client:
            resp = client.get(base_url, params=params)
            if resp.status_code != 200:
                return None
            data = resp.json()
    except Exception:
        return None
    results = data.get("results") or []
    if not results:
        return None
    disp = results[0].get("formatted")
    if not disp:
        return None
    return GeocodeResult(address=str(disp), latitude=float(latitude), longitude=float(longitude))


__all__ = ["GeocodeResult", "geocode_address", "reverse_geocode_coordinates"]
