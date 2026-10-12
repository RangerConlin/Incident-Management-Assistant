"""WGS84 <-> UTM/MGRS coordinate conversion helpers.

Implemented as pure-Python math (no pyproj dependency) so the desktop
distributable does not need to bundle PROJ's native data files. Formulas
follow the standard Snyder/NGA transverse Mercator projection used for
UTM, which is accurate to well under a meter across the working range
used here (ground search/incident mapping, not survey-grade geodesy).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

_A = 6378137.0  # WGS84 semi-major axis (m)
_F = 1 / 298.257223563  # WGS84 flattening
_K0 = 0.9996  # UTM scale factor
_E = math.sqrt(_F * (2 - _F))
_E2 = _E * _E
_E4 = _E2 * _E2
_E6 = _E2 * _E4
_EP2 = _E2 / (1 - _E2)

_MGRS_COL_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"
_MGRS_ROW_LETTERS = "ABCDEFGHJKLMNPQRSTUV"
_LAT_BANDS = "CDEFGHJKLMNPQRSTUVWXX"  # last entry (X) spans 72-84


@dataclass(frozen=True)
class UTMCoordinate:
    zone_number: int
    zone_letter: str
    easting: float
    northing: float

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return f"{self.zone_number}{self.zone_letter} {self.easting:.0f}E {self.northing:.0f}N"


def _latitude_band(lat: float) -> str:
    if lat < -80 or lat > 84:
        raise ValueError("Latitude out of UTM range (-80 to 84)")
    if lat >= 72:
        return "X"
    index = int((lat + 80) // 8)
    index = max(0, min(index, len(_LAT_BANDS) - 1))
    return _LAT_BANDS[index]


def _zone_number(lat: float, lon: float) -> int:
    zone = int((lon + 180) / 6) + 1
    # Norway/Svalbard irregular zone exceptions.
    if 56 <= lat < 64 and 3 <= lon < 12:
        zone = 32
    if 72 <= lat < 84:
        if 0 <= lon < 9:
            zone = 31
        elif 9 <= lon < 21:
            zone = 33
        elif 21 <= lon < 33:
            zone = 35
        elif 33 <= lon < 42:
            zone = 37
    return zone


def latlon_to_utm(lat: float, lon: float) -> UTMCoordinate:
    """Convert a WGS84 lat/lon (degrees) to a UTM coordinate."""
    if not (-80.0 <= lat <= 84.0):
        raise ValueError("Latitude out of UTM range (-80 to 84)")

    zone_number = _zone_number(lat, lon)
    lon_origin = math.radians((zone_number - 1) * 6 - 180 + 3)
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)

    n = _A / math.sqrt(1 - _E2 * math.sin(lat_rad) ** 2)
    t = math.tan(lat_rad) ** 2
    c = _EP2 * math.cos(lat_rad) ** 2
    a = math.cos(lat_rad) * (lon_rad - lon_origin)

    m = _A * (
        (1 - _E2 / 4 - 3 * _E4 / 64 - 5 * _E6 / 256) * lat_rad
        - (3 * _E2 / 8 + 3 * _E4 / 32 + 45 * _E6 / 1024) * math.sin(2 * lat_rad)
        + (15 * _E4 / 256 + 45 * _E6 / 1024) * math.sin(4 * lat_rad)
        - (35 * _E6 / 3072) * math.sin(6 * lat_rad)
    )

    easting = (
        _K0
        * n
        * (
            a
            + (1 - t + c) * a**3 / 6
            + (5 - 18 * t + t**2 + 72 * c - 58 * _EP2) * a**5 / 120
        )
        + 500000.0
    )

    northing = _K0 * (
        m
        + n
        * math.tan(lat_rad)
        * (
            a**2 / 2
            + (5 - t + 9 * c + 4 * c**2) * a**4 / 24
            + (61 - 58 * t + t**2 + 600 * c - 330 * _EP2) * a**6 / 720
        )
    )
    if lat < 0:
        northing += 10000000.0

    return UTMCoordinate(zone_number, _latitude_band(lat), easting, northing)


def utm_to_latlon(zone_number: int, zone_letter: str, easting: float, northing: float) -> tuple[float, float]:
    """Convert a UTM coordinate back to WGS84 lat/lon (degrees)."""
    northern = zone_letter.upper() >= "N"
    x = easting - 500000.0
    y = northing if northern else northing - 10000000.0

    m = y / _K0
    mu = m / (_A * (1 - _E2 / 4 - 3 * _E4 / 64 - 5 * _E6 / 256))

    e1 = (1 - math.sqrt(1 - _E2)) / (1 + math.sqrt(1 - _E2))
    phi1 = (
        mu
        + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
        + (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
        + (151 * e1**3 / 96) * math.sin(6 * mu)
    )

    n1 = _A / math.sqrt(1 - _E2 * math.sin(phi1) ** 2)
    t1 = math.tan(phi1) ** 2
    c1 = _EP2 * math.cos(phi1) ** 2
    r1 = _A * (1 - _E2) / (1 - _E2 * math.sin(phi1) ** 2) ** 1.5
    d = x / (n1 * _K0)

    lat_rad = phi1 - (n1 * math.tan(phi1) / r1) * (
        d**2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * _EP2) * d**4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * _EP2 - 3 * c1**2) * d**6 / 720
    )
    lon_rad = (
        d
        - (1 + 2 * t1 + c1) * d**3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * _EP2 + 24 * t1**2) * d**5 / 120
    ) / math.cos(phi1)

    lon_origin = math.radians((zone_number - 1) * 6 - 180 + 3)
    lon = math.degrees(lon_rad) + math.degrees(lon_origin)
    lat = math.degrees(lat_rad)
    return lat, lon


def latlon_to_mgrs(lat: float, lon: float, precision: int = 5) -> str:
    """Convert a WGS84 lat/lon to an MGRS grid string.

    precision: number of digits per easting/northing component (0-5),
    e.g. precision=5 -> 1 m resolution, precision=3 -> 100 m resolution.
    """
    precision = max(0, min(5, precision))
    utm = latlon_to_utm(lat, lon)

    col_index = int(utm.easting // 100000) - 1
    col_set = (utm.zone_number - 1) % 3
    col_letter = _MGRS_COL_LETTERS[(col_set * 8 + col_index) % len(_MGRS_COL_LETTERS)]

    row_index = int(utm.northing // 100000) % 20
    row_set = (utm.zone_number - 1) % 2
    row_offset = 5 if row_set == 1 else 0
    row_letter = _MGRS_ROW_LETTERS[(row_index + row_offset) % len(_MGRS_ROW_LETTERS)]

    easting_digits = int(utm.easting % 100000)
    northing_digits = int(utm.northing % 100000)

    def _fmt(value: int) -> str:
        text = f"{value:05d}"
        return text[:precision] if precision > 0 else ""

    grid_zone = f"{utm.zone_number}{utm.zone_letter}"
    hundred_km_id = f"{col_letter}{row_letter}"
    if precision == 0:
        return f"{grid_zone} {hundred_km_id}"
    return f"{grid_zone} {hundred_km_id} {_fmt(easting_digits)} {_fmt(northing_digits)}"


def format_dms(value: float, is_latitude: bool) -> str:
    """Format a decimal-degree coordinate as D° M' S\" with hemisphere suffix."""
    hemisphere = ("N" if value >= 0 else "S") if is_latitude else ("E" if value >= 0 else "W")
    magnitude = abs(value)
    degrees = int(magnitude)
    minutes_full = (magnitude - degrees) * 60
    minutes = int(minutes_full)
    seconds = (minutes_full - minutes) * 60
    return f"{degrees}°{minutes}'{seconds:.2f}\"{hemisphere}"


__all__ = [
    "UTMCoordinate",
    "latlon_to_utm",
    "utm_to_latlon",
    "latlon_to_mgrs",
    "format_dms",
]
