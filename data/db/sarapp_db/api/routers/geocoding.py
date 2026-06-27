from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sarapp_db.services.geocoding import geocode_address, geocode_to_dict, reverse_geocode_coordinates

router = APIRouter()


class GeocodeRequest(BaseModel):
    address: str


class ReverseGeocodeRequest(BaseModel):
    latitude: float
    longitude: float


@router.post("/geocode")
def geocode(request: GeocodeRequest) -> dict:
    result = geocode_address(request.address)
    if result is None:
        raise HTTPException(status_code=404, detail="Geocoding did not return a match")
    return geocode_to_dict(result) or {}


@router.post("/reverse-geocode")
def reverse_geocode(request: ReverseGeocodeRequest) -> dict:
    result = reverse_geocode_coordinates(request.latitude, request.longitude)
    if result is None:
        raise HTTPException(status_code=404, detail="Reverse geocoding did not return a match")
    return geocode_to_dict(result) or {}
