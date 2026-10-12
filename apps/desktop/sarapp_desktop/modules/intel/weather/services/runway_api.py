"""Live runway lookup via NOAA's Aviation Weather Center (AWC) airport data API.

https://aviationweather.gov/api/data/airport?ids={icao}&format=json — the
same host already used for METAR/TAF (data_providers/noaa_metar_taf.py), so
this adds no new provider, no API key, and no new secret to manage. Queried
once when a station is created (weather_manager.add_manual_location /
sync_auto_locations) and cached on the WeatherLocation — never re-queried
per crosswind computation.

AWC's airport payload gives one `runways` entry per physical runway, e.g.
`{"id": "08L/26R", "alignment": "080", "dimension": "12000x150"}` — a single
true-heading `alignment` for the lower-numbered end; the reciprocal end is
derived as `alignment + 180`, not a second value the API returns.

Never fabricates: any lookup failure (network error, unknown ICAO code,
unexpected response shape) returns an empty list, and callers simply omit
the crosswind readout rather than guessing.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..data_providers.base import get_shared_client
from ..models.location import RunwayEnd

LOGGER = logging.getLogger(__name__)

_AWC_AIRPORT_URL = "https://aviationweather.gov/api/data/airport"


def fetch_airport(icao_code: str) -> Optional[Dict[str, Any]]:
    """Query AWC's airport endpoint for one ICAO code's identity + runways.

    Returns None (never a guess) if the airport isn't found or the request
    fails for any reason. Used both for station-creation runway lookups and
    for the Aviation tab's "add by identifier" flow, which also needs the
    airport's name and coordinates.
    """
    code = (icao_code or "").strip().upper()
    if not code:
        return None
    try:
        client = get_shared_client()
        resp = client.get(_AWC_AIRPORT_URL, params={"ids": code, "format": "json"})
        if resp.status_code != 200:
            LOGGER.warning("AWC airport lookup HTTP %s for %s", resp.status_code, code)
            return None
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Failed to fetch airport data for %s: %s", code, exc)
        return None

    airport = _first_matching_airport(payload, code)
    if airport is None:
        return None

    try:
        latitude = float(airport.get("lat")) if airport.get("lat") is not None else None
    except (TypeError, ValueError):
        latitude = None
    try:
        longitude = float(airport.get("lon")) if airport.get("lon") is not None else None
    except (TypeError, ValueError):
        longitude = None

    return {
        "icao": str(airport.get("icaoId") or code).strip().upper(),
        "name": str(airport.get("name") or airport.get("site") or code).strip(),
        "latitude": latitude,
        "longitude": longitude,
        "runway_ends": _parse_runways(airport.get("runways") or []),
    }


def fetch_runways(icao_code: str) -> List[RunwayEnd]:
    """Query AWC's airport endpoint for one ICAO code's published runways.

    Returns an empty list (never a guess) if the airport isn't found, has no
    runway data, or the request fails for any reason.
    """
    info = fetch_airport(icao_code)
    return info["runway_ends"] if info is not None else []


def _first_matching_airport(payload: Any, icao_code: str) -> Dict[str, Any] | None:
    items: List[Dict[str, Any]]
    if isinstance(payload, list):
        items = [x for x in payload if isinstance(x, dict)]
    elif isinstance(payload, dict):
        items = [payload]
    else:
        return None
    for item in items:
        item_id = str(item.get("icaoId") or item.get("id") or "").strip().upper()
        if not item_id or item_id == icao_code:
            return item
    return items[0] if items else None


def _parse_runways(entries: List[Dict[str, Any]]) -> List[RunwayEnd]:
    ends: List[RunwayEnd] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        try:
            designators = str(entry.get("id") or "").split("/")
            alignment = float(entry.get("alignment"))
        except (TypeError, ValueError):
            LOGGER.warning("Skipping runway entry with no usable alignment: %s", entry)
            continue

        length_ft = None
        dimension = str(entry.get("dimension") or "")
        if "x" in dimension.lower():
            try:
                length_ft = float(dimension.lower().split("x")[0])
            except ValueError:
                length_ft = None

        if len(designators) == 2 and designators[0] and designators[1]:
            ends.append(RunwayEnd(designator=designators[0], heading_true_deg=alignment % 360, length_ft=length_ft))
            ends.append(
                RunwayEnd(designator=designators[1], heading_true_deg=(alignment + 180) % 360, length_ft=length_ft)
            )
        elif designators and designators[0]:
            ends.append(RunwayEnd(designator=designators[0], heading_true_deg=alignment % 360, length_ft=length_ft))
    return ends


__all__ = ["fetch_airport", "fetch_runways"]
