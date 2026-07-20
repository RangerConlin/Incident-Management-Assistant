"""Draw tool geometry helpers: Point/Line/Arc/Polygon/Rectangle/Circle/Ring.

The actual on-map vertex collection happens in Leaflet/JS (map_canvas.py
wires the JS draw handlers and receives finished vertex lists back through
the QWebChannel bridge); this module turns those vertex lists into WKT and
implements the one piece of real, unit-testable logic in the milestone: the
Ring tool's comma-separated distance-list parser.
"""

from __future__ import annotations

from dataclasses import dataclass

_RING_MIN_DISTANCE = 1e-9


def parse_ring_distances(raw_text: str) -> list[float]:
    """Parse a comma-separated distance list for the Ring tool.

    Rules (per plan): parse each token as a number, silently drop tokens
    that aren't valid numbers, reject/drop zero and negative values, dedupe
    equal values, and return the remaining distances numerically sorted
    ascending. Never raises — invalid input just yields fewer rings.
    """
    if not raw_text:
        return []
    seen: set[float] = set()
    values: list[float] = []
    for token in raw_text.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            value = float(token)
        except ValueError:
            continue
        if value <= _RING_MIN_DISTANCE:
            continue
        if value in seen:
            continue
        seen.add(value)
        values.append(value)
    return sorted(values)


def points_to_wkt(coords: list[tuple[float, float]]) -> str:
    """coords is a list of (lon, lat) pairs -> POINT WKT for a single vertex."""
    if not coords:
        raise ValueError("Point geometry requires exactly one vertex.")
    lon, lat = coords[0]
    return f"POINT({lon:.7f} {lat:.7f})"


def line_to_wkt(coords: list[tuple[float, float]]) -> str:
    if len(coords) < 2:
        raise ValueError("Line geometry requires at least two vertices.")
    body = ", ".join(f"{lon:.7f} {lat:.7f}" for lon, lat in coords)
    return f"LINESTRING({body})"


def polygon_to_wkt(coords: list[tuple[float, float]]) -> str:
    if len(coords) < 3:
        raise ValueError("Polygon geometry requires at least three vertices.")
    ring = list(coords)
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    body = ", ".join(f"{lon:.7f} {lat:.7f}" for lon, lat in ring)
    return f"POLYGON(({body}))"


def rectangle_to_wkt(sw: tuple[float, float], ne: tuple[float, float]) -> str:
    (sw_lon, sw_lat), (ne_lon, ne_lat) = sw, ne
    coords = [
        (sw_lon, sw_lat),
        (ne_lon, sw_lat),
        (ne_lon, ne_lat),
        (sw_lon, ne_lat),
        (sw_lon, sw_lat),
    ]
    body = ", ".join(f"{lon:.7f} {lat:.7f}" for lon, lat in coords)
    return f"POLYGON(({body}))"


@dataclass(frozen=True)
class RingSpec:
    center: tuple[float, float]
    distances_m: list[float]
    unit: str
    labels: bool = True


DRAW_TOOL_KEYS = (
    "draw_point",
    "draw_line",
    "draw_arc",
    "draw_polygon",
    "draw_rectangle",
    "draw_circle",
    "draw_ring",
)
