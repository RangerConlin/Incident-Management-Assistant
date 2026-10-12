from __future__ import annotations

from enum import Enum


class GeometryType(str, Enum):
    """Supported geometry primitives for spatial features."""

    POINT = "POINT"
    LINE = "LINE"
    POLYGON = "POLYGON"
