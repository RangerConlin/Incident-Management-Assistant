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

    def _cached_facility_docs(self) -> Optional[list[dict]]:
        from utils.incident_cache import incident_cache

        if incident_cache.incident_id != self.incident_id:
            return None
        return incident_cache.get_all("facilities")

    def _cached_facility_doc(self, facility_id: str) -> Optional[dict]:
        cached = self._cached_facility_docs()
        if cached is None:
            return None
        for doc in cached:
            if str(doc.get("_id")) == str(facility_id):
                return dict(doc)
        return None

    @staticmethod
    def _normalize_doc(doc: dict) -> dict:
        return {**doc, "id": str(doc.get("id") or doc.get("_id") or "")}

    def list_facilities(
        self,
        *,
        facility_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[FacilityRecord]:
        cached = self._cached_facility_docs()
        if cached is not None:
            filtered = cached
            if facility_type:
                filtered = [d for d in filtered if d.get("facility_type") == facility_type]
            if status:
                filtered = [d for d in filtered if d.get("status") == status]
            ordered = sorted(
                filtered,
                key=lambda d: (str(d.get("facility_type") or ""), str(d.get("name") or "")),
            )
            rows = [self._normalize_doc(d) for d in ordered]
        else:
            rows = api_client.get(self._base, params={"facility_type": facility_type, "status": status}) or []
        return [FacilityRecord.from_api(row) for row in rows]

    def get_facility(self, facility_id: str) -> FacilityRecord | None:
        cached = self._cached_facility_doc(facility_id)
        if cached is not None:
            return FacilityRecord.from_api(self._normalize_doc(cached))
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
