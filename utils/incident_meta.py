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
        facility_id = str(doc.get("icp_facility_id") or "")
        if not facility_id:
            return None
        facility = api_client.get(f"/api/incidents/{incident_id}/facilities/{facility_id}") or {}
        address = str(facility.get("name") or facility.get("address") or "")
        lat = facility.get("latitude")
        lon = facility.get("longitude")
        if not address or lat is None or lon is None:
            return None
        return IcpLocation(address=address, latitude=float(lat), longitude=float(lon))
    except Exception:
        return None


__all__ = ["IcpLocation", "get_icp_location"]
