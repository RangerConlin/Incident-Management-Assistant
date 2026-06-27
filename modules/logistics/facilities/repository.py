from __future__ import annotations

from typing import Optional

from utils.api_client import api_client
from utils.state import AppState
from .models import FacilityRecord


def _active_incident_id(incident_id: str | None = None) -> str:
    value = incident_id or AppState.get_active_incident()
    return str(value or "")


class ApiFacilitiesRepository:
    def __init__(self, incident_id: Optional[str] = None) -> None:
        self.incident_id = _active_incident_id(incident_id)

    @property
    def _base(self) -> str:
        if not self.incident_id:
            raise RuntimeError("No active incident selected")
        return f"/api/incidents/{self.incident_id}/facilities"

    def list_facilities(
        self,
        *,
        facility_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[FacilityRecord]:
        rows = api_client.get(self._base, params={"facility_type": facility_type, "status": status}) or []
        return [FacilityRecord.from_api(row) for row in rows]

    def get_facility(self, facility_id: str) -> FacilityRecord | None:
        try:
            row = api_client.get(f"{self._base}/{facility_id}")
        except Exception:
            return None
        return FacilityRecord.from_api(row)

    def save_facility(self, facility: FacilityRecord) -> FacilityRecord:
        payload = facility.to_api_payload()
        if facility.id:
            row = api_client.put(f"{self._base}/{facility.id}", json=payload)
        else:
            row = api_client.post(self._base, json=payload)
        return FacilityRecord.from_api(row)

    def delete_facility(self, facility_id: str) -> bool:
        result = api_client.delete(f"{self._base}/{facility_id}") or {}
        return bool(result.get("ok"))


__all__ = ["ApiFacilitiesRepository", "FacilityRecord"]
