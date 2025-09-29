from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import httpx


DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class HttpClient:
    """Thin wrapper around httpx for simpler mocking in tests."""

    def __init__(self) -> None:
        self._client = httpx.Client(timeout=DEFAULT_TIMEOUT, headers={
            "User-Agent": "Incident-Management-Assistant/WeatherSafety (https://github.com)"
        })

    def get_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        r = self._client.get(url, params=params)
        r.raise_for_status()
        return r.json()

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass


def nws_points(client: HttpClient, lat: float, lon: float) -> Dict[str, Any]:
    return client.get_json(f"https://api.weather.gov/points/{lat},{lon}")


def nws_forecast(client: HttpClient, points_payload: Dict[str, Any], hourly: bool = False) -> Dict[str, Any]:
    props = points_payload.get("properties", {})
    url = props.get("forecastHourly") if hourly else props.get("forecast")
    if not url:
        raise RuntimeError("NWS points payload missing forecast URL")
    return client.get_json(url)


def nws_current_conditions(client: HttpClient, points_payload: Dict[str, Any]) -> Dict[str, Any]:
    props = points_payload.get("properties", {})
    stations_url = props.get("observationStations")
    if not stations_url:
        return {}
    stations = client.get_json(stations_url)
    first = (stations.get("features") or [{}])[0]
    obs_url = first.get("id", "") + "/observations/latest"
    if not obs_url:
        return {}
    return client.get_json(obs_url)


def nws_active_alerts(client: HttpClient, lat: float, lon: float) -> Dict[str, Any]:
    return client.get_json("https://api.weather.gov/alerts/active", params={"point": f"{lat},{lon}"})


def nws_hwo_latest(client: HttpClient, points_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Fetch latest Hazardous Weather Outlook for the local WFO if available.

    Uses the "cwa" (WFO) from points payload when present.
    """
    cwa = (points_payload.get("properties", {}).get("cwa") or "").strip()
    if not cwa:
        return None
    listing = client.get_json("https://api.weather.gov/products/types/HWO")
    # Narrow by location if server supports it; otherwise fetch recent list and pick by WFO
    try:
        products = client.get_json("https://api.weather.gov/products", params={"types": "HWO", "locations": cwa})
    except Exception:
        products = client.get_json("https://api.weather.gov/products", params={"types": "HWO"})
    items = products.get("@graph") or []
    for p in items:
        if p.get("office") and cwa in p.get("office"):
            pid = p.get("id")
            if not pid:
                continue
            try:
                return client.get_json(pid)
            except Exception:
                continue
    return None


def adds_metar(client: HttpClient, stations: List[str], hours_before_now: int = 2) -> Dict[str, Any]:
    station_str = ",".join([s.strip().upper() for s in stations if s.strip()])
    if not station_str:
        return {"data": []}
    return client.get_json(
        "https://aviationweather.gov/adds/dataserver_current/httpparam",
        params={
            "datasource": "metars",
            "requestType": "retrieve",
            "format": "JSON",
            "hoursBeforeNow": str(hours_before_now),
            "stationString": station_str,
        },
    )


def adds_taf(client: HttpClient, stations: List[str], hours_before_now: int = 6) -> Dict[str, Any]:
    station_str = ",".join([s.strip().upper() for s in stations if s.strip()])
    if not station_str:
        return {"data": []}
    return client.get_json(
        "https://aviationweather.gov/adds/dataserver_current/httpparam",
        params={
            "datasource": "tafs",
            "requestType": "retrieve",
            "format": "JSON",
            "hoursBeforeNow": str(hours_before_now),
            "stationString": station_str,
        },
    )

