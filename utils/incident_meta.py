from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from utils import incident_context


@dataclass
class IcpLocation:
    address: str
    latitude: float
    longitude: float


def get_icp_location() -> Optional[IcpLocation]:
    incident_id = incident_context.get_active_incident_id()
    if not incident_id:
        return None
    try:
        from utils.api_client import api_client

        doc = api_client.get(f"/api/incidents/{incident_id}/profile") or {}
        address = doc.get("icp_location") or ""
        lat = doc.get("latitude")
        lon = doc.get("longitude")
        if not address or lat is None or lon is None:
            return None
        return IcpLocation(address=address, latitude=float(lat), longitude=float(lon))
    except Exception:
        return None


def set_icp_location(address: str, latitude: float, longitude: float) -> None:
    incident_id = incident_context.get_active_incident_id()
    if not incident_id:
        raise RuntimeError("No active incident")
    from utils.api_client import api_client

    api_client.patch(
        f"/api/incidents/{incident_id}/profile",
        json={"icp_location": address, "latitude": float(latitude), "longitude": float(longitude)},
    )

    try:
        from utils.app_signals import app_signals

        app_signals.icpLocationChanged.emit(
            {"address": address, "lat": float(latitude), "lon": float(longitude)}
        )
    except Exception:
        pass


__all__ = ["IcpLocation", "get_icp_location", "set_icp_location"]
