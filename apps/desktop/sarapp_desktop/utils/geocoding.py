from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from utils.api_client import APIError, api_client


@dataclass
class GeocodeResult:
    address: str
    latitude: float
    longitude: float


def geocode_address(address: str) -> Optional[GeocodeResult]:
    addr = address.strip()
    if not addr:
        return None
    try:
        data = api_client.post("/api/geocoding/geocode", json={"address": addr})
    except APIError:
        return None
    return GeocodeResult(
        address=str(data.get("address") or addr),
        latitude=float(data["latitude"]),
        longitude=float(data["longitude"]),
    )


def reverse_geocode_coordinates(latitude: float, longitude: float) -> Optional[GeocodeResult]:
    try:
        data = api_client.post(
            "/api/geocoding/reverse-geocode",
            json={"latitude": float(latitude), "longitude": float(longitude)},
        )
    except APIError:
        return None
    return GeocodeResult(
        address=str(data.get("address") or ""),
        latitude=float(data["latitude"]),
        longitude=float(data["longitude"]),
    )


__all__ = ["GeocodeResult", "geocode_address", "reverse_geocode_coordinates"]
