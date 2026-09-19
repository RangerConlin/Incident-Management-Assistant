"""Find ambulance services near a point.

Ambulance services come from the Esri U.S. Federal Datasets "Structures -
Medical Emergency Response" feature service (USGS National Structures data).
Records carry only a name, street address and coordinates: no phone number or
ALS/BLS level, and the underlying load dates can be years old.  Treat results
as candidates for a preparer to review, not as authoritative data.
"""

from __future__ import annotations

from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Any

# Only ambulance services come from this source.  Hospitals use the CMS-backed
# directory in hospital_directory.py, which knows which hospitals have an ER.
SERVICE_URL = (
    "https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/"
    "Structures_Medical_Emergency_Response_v1/FeatureServer"
)
SOURCE_LABEL = "Esri U.S. Federal Datasets (USGS Structures)"
SOURCE_PREFIX = "usgs_structures"

# API kind -> feature service layer id
LAYERS: dict[str, int] = {"ambulance-services": 1}

MAX_RADIUS_MI = 100.0
_PAGE_LIMIT = 1000
_MAX_PAGES = 5
_TIMEOUT_S = 15.0
_OUT_FIELDS = "PERMANENT_IDENTIFIER,NAME,ADDRESS,CITY,STATE,ZIPCODE,LOADDATE"


class NearbyLookupError(RuntimeError):
    """The upstream feature service could not be queried."""


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return 2 * 3958.8 * asin(sqrt(a))


def _full_address(attrs: dict[str, Any]) -> str:
    street = str(attrs.get("ADDRESS") or "").strip()
    state_zip = " ".join(part for part in (str(attrs.get("STATE") or "").strip(), str(attrs.get("ZIPCODE") or "").strip()) if part)
    return ", ".join(part for part in (street, str(attrs.get("CITY") or "").strip(), state_zip) if part)


def _source_date(load_date_ms: Any) -> str:
    try:
        return datetime.fromtimestamp(int(load_date_ms) / 1000, tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


def find_nearby(kind: str, latitude: float, longitude: float, radius_mi: float) -> list[dict[str, Any]]:
    """Return facilities of ``kind`` within ``radius_mi`` miles, nearest first."""
    try:
        layer = LAYERS[kind]
    except KeyError as exc:
        raise ValueError(f"Unknown kind: {kind}") from exc
    radius_mi = max(0.1, min(float(radius_mi), MAX_RADIUS_MI))

    try:
        import httpx
    except Exception as exc:
        raise RuntimeError("httpx is not installed. Install with: pip install httpx") from exc

    params = {
        "f": "json",
        "where": "1=1",
        "geometry": f"{longitude},{latitude}",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "distance": radius_mi,
        "units": "esriSRUnit_StatuteMile",
        "outFields": _OUT_FIELDS,
        "outSR": 4326,
        "returnGeometry": "true",
        "resultRecordCount": _PAGE_LIMIT,
    }
    features: list[dict[str, Any]] = []
    try:
        with httpx.Client(timeout=httpx.Timeout(_TIMEOUT_S)) as client:
            for page in range(_MAX_PAGES):
                resp = client.get(f"{SERVICE_URL}/{layer}/query", params={**params, "resultOffset": page * _PAGE_LIMIT})
                resp.raise_for_status()
                body = resp.json()
                if "error" in body:
                    raise NearbyLookupError(str(body["error"].get("message") or body["error"]))
                features.extend(body.get("features") or [])
                if not body.get("exceededTransferLimit"):
                    break
    except NearbyLookupError:
        raise
    except Exception as exc:
        raise NearbyLookupError(f"Could not reach the facility lookup service: {exc}") from exc

    results: list[dict[str, Any]] = []
    for feature in features:
        attrs = feature.get("attributes") or {}
        geom = feature.get("geometry") or {}
        lat, lon = geom.get("y"), geom.get("x")
        name = str(attrs.get("NAME") or "").strip()
        if lat is None or lon is None or not name:
            continue
        results.append({
            "source_ref": f"{SOURCE_PREFIX}:{attrs.get('PERMANENT_IDENTIFIER') or name}",
            "name": name,
            "address": _full_address(attrs),
            "lat": float(lat),
            "lon": float(lon),
            "distance_mi": round(_haversine_miles(latitude, longitude, float(lat), float(lon)), 1),
            "source_date": _source_date(attrs.get("LOADDATE")),
            "source": SOURCE_LABEL,
        })
    return sorted(results, key=lambda row: (row["distance_mi"], row["name"]))
