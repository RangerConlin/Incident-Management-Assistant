"""Emergency-department hospital directory built from CMS Hospital General Information.

CMS publishes every Medicare-certified hospital with an ``emergency_services``
Yes/No flag, refreshed regularly, so closed hospitals and prison hospitals drop
out on their own.  The feed has street addresses but no coordinates and no
distance search, so this module:

1. works out which states a search circle touches (Census TIGERweb),
2. refreshes any state whose cached copy is missing or older than
   ``REFRESH_TTL`` (CMS query + Census batch geocoding), and
3. answers the radius search from the cached copy in the master database.

Once a state is cached, searching works without internet; only refreshing needs
CMS and the geocoder.  The cache lives in its own collection
(``hospital_directory``), separate from the curated master ``hospitals`` list.
Trauma level, helipad and burn-center status are not in the CMS feed.
"""

from __future__ import annotations

import csv
import io
import logging
import re
import threading
from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Any, Callable, Optional

from pymongo.database import Database

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.repository import BaseRepository
from sarapp_db.services.geocoding import geocode_address
from sarapp_db.services.nearby_medical import NearbyLookupError

logger = logging.getLogger(__name__)

CMS_URL = "https://data.cms.gov/provider-data/api/1/datastore/query/xubh-q36u/0"
TIGERWEB_STATES_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/0/query"
)
CENSUS_BATCH_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
TIGERWEB_ZCTA_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/PUMA_TAD_TAZ_UGA_ZCTA/MapServer/1/query"
)

SOURCE_LABEL = "CMS Hospital General Information (Medicare-certified hospitals with emergency services)"
SOURCE_PREFIX = "cms"
REFRESH_TTL = timedelta(days=30)
_PAGE_LIMIT = 500
_TIMEOUT_S = 30.0
_BATCH_TIMEOUT_S = 120.0
_MAX_UNLOCATED_LISTED = 8

_refresh_lock = threading.Lock()


class HospitalDirectoryRepository(BaseRepository):
    collection_name = MasterCollections.HOSPITAL_DIRECTORY
    soft_deletes = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return 2 * 3958.8 * asin(sqrt(a))


_SMALL_WORDS = {"of", "and", "the", "at", "in", "for", "to"}


def _display_case(text: str) -> str:
    """CMS sends names and addresses in capitals; make them readable."""
    text = (text or "").strip()
    if not text or text != text.upper():
        return text
    words = []
    for index, word in enumerate(text.lower().split()):
        word = word if (index and word in _SMALL_WORDS) else word.capitalize()
        words.append(re.sub(r"^(\d+)(St|Nd|Rd|Th)$", lambda m: m.group(1) + m.group(2).lower(), word))
    return " ".join(words)


def _street_for_geocoding(address: str) -> str:
    """CMS spells some street numbers out ("ONE GENESYS PARKWAY")."""
    return re.sub(r"^ONE\b", "1", address.strip(), flags=re.IGNORECASE)


# ---------------------------------------------------------------------------
# External calls (each kept small so tests can replace them)
# ---------------------------------------------------------------------------

def states_within(latitude: float, longitude: float, radius_mi: float) -> list[str]:
    """State abbreviations whose territory intersects the search circle."""
    import httpx

    params = {
        "f": "json",
        "where": "1=1",
        "geometry": f"{longitude},{latitude}",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "distance": radius_mi,
        "units": "esriSRUnit_StatuteMile",
        "outFields": "STUSAB",
        "returnGeometry": "false",
    }
    try:
        resp = httpx.get(TIGERWEB_STATES_URL, params=params, timeout=_TIMEOUT_S)
        resp.raise_for_status()
        body = resp.json()
    except Exception as exc:
        raise NearbyLookupError(f"Could not determine which states are nearby: {exc}") from exc
    states = sorted({str(f["attributes"]["STUSAB"]) for f in body.get("features") or [] if f.get("attributes")})
    if not states:
        raise NearbyLookupError("The incident location is not inside a US state or territory.")
    return states


def fetch_cms_er_hospitals(state: str) -> list[dict[str, Any]]:
    """Every CMS-listed hospital in ``state`` that reports emergency services."""
    import httpx

    rows: list[dict[str, Any]] = []
    try:
        with httpx.Client(timeout=httpx.Timeout(_TIMEOUT_S)) as client:
            while True:
                resp = client.get(CMS_URL, params={
                    "limit": _PAGE_LIMIT,
                    "offset": len(rows),
                    "conditions[0][property]": "state",
                    "conditions[0][value]": state,
                    "conditions[1][property]": "emergency_services",
                    "conditions[1][value]": "Yes",
                })
                resp.raise_for_status()
                page = resp.json().get("results") or []
                rows.extend(page)
                if len(page) < _PAGE_LIMIT:
                    break
    except Exception as exc:
        raise NearbyLookupError(f"Could not reach the CMS hospital directory: {exc}") from exc
    return rows


def batch_geocode(addresses: dict[str, tuple[str, str, str, str]]) -> dict[str, tuple[float, float]]:
    """Geocode ``{id: (street, city, state, zip)}`` in one Census batch request."""
    if not addresses:
        return {}
    import httpx

    buf = io.StringIO()
    writer = csv.writer(buf)
    for key, (street, city, state, zip_code) in addresses.items():
        writer.writerow([key, street, city, state, zip_code])
    try:
        resp = httpx.post(
            CENSUS_BATCH_URL,
            data={"benchmark": "Public_AR_Current"},
            files={"addressFile": ("addresses.csv", buf.getvalue(), "text/csv")},
            timeout=_BATCH_TIMEOUT_S,
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("Census batch geocoding failed, falling back to single lookups: %s", exc)
        return {}
    located: dict[str, tuple[float, float]] = {}
    for record in csv.reader(io.StringIO(resp.text)):
        if len(record) > 5 and record[2] == "Match" and record[5]:
            lon, lat = record[5].split(",")
            located[record[0]] = (float(lat), float(lon))
    return located


def zip_centroids(zip_codes: set[str]) -> dict[str, tuple[float, float]]:
    """Approximate location (ZIP area centre) for hospitals no geocoder could place."""
    zips = sorted({z[:5] for z in zip_codes if z and z[:5].isdigit()})
    if not zips:
        return {}
    import httpx

    where = "ZCTA5 IN (" + ",".join(f"'{z}'" for z in zips) + ")"
    try:
        resp = httpx.post(
            TIGERWEB_ZCTA_URL,
            data={"f": "json", "where": where, "outFields": "ZCTA5,INTPTLAT,INTPTLON", "returnGeometry": "false"},
            timeout=_TIMEOUT_S,
        )
        resp.raise_for_status()
        features = resp.json().get("features") or []
    except Exception as exc:
        logger.warning("ZIP centroid lookup failed: %s", exc)
        return {}
    return {
        str(f["attributes"]["ZCTA5"]): (float(f["attributes"]["INTPTLAT"]), float(f["attributes"]["INTPTLON"]))
        for f in features
        if f.get("attributes")
    }


# ---------------------------------------------------------------------------
# Directory
# ---------------------------------------------------------------------------

class HospitalDirectory:
    def __init__(self, master_db: Database) -> None:
        self._repo = HospitalDirectoryRepository(master_db)

    # -- refresh ------------------------------------------------------------
    def _state_docs(self, state: str) -> list[dict[str, Any]]:
        return self._repo.find_many({"state": state})

    def _is_stale(self, state: str) -> bool:
        seen = [doc.get("last_seen_at") for doc in self._state_docs(state) if doc.get("last_seen_at")]
        if not seen:
            return True
        return _now() - datetime.fromisoformat(max(seen)) > REFRESH_TTL

    def refresh_state(self, state: str) -> int:
        """Re-read CMS for ``state``, geocode anything new, and retire hospitals CMS dropped."""
        with _refresh_lock:
            cms_rows = fetch_cms_er_hospitals(state)
            existing = {doc["cms_id"]: doc for doc in self._state_docs(state)}
            now = _iso(_now())

            needs_geocode: dict[str, tuple[str, str, str, str]] = {}
            for row in cms_rows:
                cms_id = str(row["facility_id"])
                address = f"{row['address']}, {row['citytown']}, {row['state']}, {row['zip_code']}"
                previous = existing.get(cms_id)
                if (
                    previous is None
                    or previous.get("source_address") != address
                    or previous.get("lat") is None
                    or previous.get("location_approximate")
                ):
                    needs_geocode[cms_id] = (
                        _street_for_geocoding(row["address"]), row["citytown"], row["state"], row["zip_code"],
                    )

            coordinates = batch_geocode(needs_geocode)
            for cms_id, (street, city, state_code, zip_code) in needs_geocode.items():
                if cms_id in coordinates:
                    continue
                one_line = f"{street}, {city}, {state_code} {zip_code}"
                try:
                    result = geocode_address(one_line)
                except Exception as exc:
                    logger.warning("Geocoding %s failed: %s", one_line, exc)
                    result = None
                if result is not None:
                    coordinates[cms_id] = (result.latitude, result.longitude)

            # Last resort: the ZIP area's centre, flagged as approximate.
            approximate: set[str] = set()
            unplaced = {cms_id: needs_geocode[cms_id][3] for cms_id in needs_geocode if cms_id not in coordinates}
            if unplaced:
                centroids = zip_centroids(set(unplaced.values()))
                for cms_id, zip_code in unplaced.items():
                    if zip_code[:5] in centroids:
                        coordinates[cms_id] = centroids[zip_code[:5]]
                        approximate.add(cms_id)

            seen: set[str] = set()
            for row in cms_rows:
                cms_id = str(row["facility_id"])
                seen.add(cms_id)
                address = f"{row['address']}, {row['citytown']}, {row['state']}, {row['zip_code']}"
                fields: dict[str, Any] = {
                    "name": _display_case(row["facility_name"]),
                    "address": _display_case(row["address"]),
                    "city": _display_case(row["citytown"]),
                    "state": row["state"],
                    "zip": row["zip_code"],
                    "county": _display_case(row.get("countyparish") or ""),
                    "phone": (row.get("telephone_number") or "").strip(),
                    "hospital_type": row.get("hospital_type") or "",
                    "ownership": row.get("hospital_ownership") or "",
                    "source_address": address,
                    "active": True,
                    "last_seen_at": now,
                }
                previous = existing.get(cms_id)
                if cms_id in coordinates:
                    fields["lat"], fields["lon"] = coordinates[cms_id]
                    fields["location_approximate"] = cms_id in approximate
                elif previous is None:
                    fields["lat"], fields["lon"] = None, None
                if previous is None:
                    self._repo.insert_one({"cms_id": cms_id, **fields})
                else:
                    self._repo.update_one(previous["_id"], fields)

            for cms_id, doc in existing.items():
                if cms_id not in seen and doc.get("active") is not False:
                    self._repo.update_one(doc["_id"], {"active": False})
            return len(cms_rows)

    # -- search -------------------------------------------------------------
    def find_nearby(
        self,
        latitude: float,
        longitude: float,
        radius_mi: float,
        *,
        refresh: bool = False,
        states: Optional[list[str]] = None,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Return (hospitals nearest first, warnings)."""
        states = states or states_within(latitude, longitude, radius_mi)
        warnings: list[str] = []
        for state in states:
            if not (refresh or self._is_stale(state)):
                continue
            try:
                self.refresh_state(state)
            except NearbyLookupError as exc:
                cached = self._state_docs(state)
                if not cached:
                    raise
                as_of = max((d.get("last_seen_at") or "" for d in cached), default="")[:10]
                warnings.append(f"Could not refresh {state} hospital data ({exc}). Showing data from {as_of}.")

        results: list[dict[str, Any]] = []
        unlocated: list[str] = []
        for doc in self._repo.find_many({"state": {"$in": states}, "active": True}):
            if doc.get("lat") is None or doc.get("lon") is None:
                unlocated.append(f"{doc['name']} ({doc['city']}, {doc['state']})")
                continue
            distance = _haversine_miles(latitude, longitude, doc["lat"], doc["lon"])
            if distance > radius_mi:
                continue
            results.append({
                "source_ref": f"{SOURCE_PREFIX}:{doc['cms_id']}",
                "name": doc["name"],
                "address": ", ".join(p for p in (doc["address"], doc["city"], f"{doc['state']} {doc['zip']}".strip()) if p),
                "phone": doc.get("phone") or "",
                "lat": doc["lat"],
                "lon": doc["lon"],
                "location_approximate": bool(doc.get("location_approximate")),
                "distance_mi": round(distance, 1),
                "source_date": str(doc.get("last_seen_at") or "")[:10],
                "source": SOURCE_LABEL,
            })
        if unlocated:
            listed = ", ".join(sorted(unlocated)[:_MAX_UNLOCATED_LISTED])
            more = len(unlocated) - _MAX_UNLOCATED_LISTED
            warnings.append(
                f"{len(unlocated)} emergency hospital(s) could not be located on the map and are not shown: "
                f"{listed}{f' and {more} more' if more > 0 else ''}."
            )
        return sorted(results, key=lambda row: (row["distance_mi"], row["name"])), warnings
