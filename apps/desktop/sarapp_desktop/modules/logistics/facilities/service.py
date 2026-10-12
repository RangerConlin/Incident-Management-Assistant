from __future__ import annotations

from dataclasses import replace
from typing import Optional

from utils.geocoding import geocode_address, reverse_geocode_coordinates
from utils.state import AppState

from .models import FACILITY_STATUSES, FACILITY_TYPES, FacilityRecord
from .repository import ApiFacilitiesRepository


class FacilitiesService:
    def __init__(
        self,
        incident_id: Optional[str] = None,
        repository: ApiFacilitiesRepository | None = None,
    ) -> None:
        resolved_incident_id = str(incident_id or AppState.get_active_incident() or "")
        self.incident_id = resolved_incident_id
        self.repository = repository or ApiFacilitiesRepository(resolved_incident_id)

    def list_facilities(
        self,
        *,
        facility_type: Optional[str] = None,
        status: Optional[str] = None,
        text_search: str = "",
    ) -> list[FacilityRecord]:
        rows = self.repository.list_facilities(facility_type=facility_type, status=status)
        query = text_search.strip().lower()
        if not query:
            return rows
        filtered: list[FacilityRecord] = []
        for row in rows:
            haystack = " | ".join(
                filter(
                    None,
                    [
                        row.name,
                        row.facility_type,
                        row.address,
                        row.geocoded_address,
                        row.contact_name,
                        row.notes,
                        ", ".join(row.function_tags),
                        ", ".join(row.served_sections),
                    ],
                )
            ).lower()
            if query in haystack:
                filtered.append(row)
        return filtered

    def get_facility(self, facility_id: str) -> FacilityRecord | None:
        return self.repository.get_facility(facility_id)

    def save_facility(self, facility: FacilityRecord) -> FacilityRecord:
        self._validate(facility)
        normalized = self._normalize(facility)
        return self.repository.save_facility(normalized)

    def delete_facility(self, facility_id: str) -> bool:
        return self.repository.delete_facility(facility_id)

    def geocode_facility(self, facility: FacilityRecord) -> FacilityRecord:
        if not facility.address.strip():
            raise ValueError("Address is required before geocoding.")
        result = geocode_address(facility.address)
        if result is None:
            raise ValueError("Geocoding did not return a match.")
        return replace(
            facility,
            latitude=result.latitude,
            longitude=result.longitude,
            geocoded_address=result.address,
        )

    def reverse_geocode_facility(self, facility: FacilityRecord) -> FacilityRecord:
        if facility.latitude is None or facility.longitude is None:
            raise ValueError("Latitude and longitude are required before reverse geocoding.")
        result = reverse_geocode_coordinates(facility.latitude, facility.longitude)
        if result is None:
            raise ValueError("Reverse geocoding did not return a match.")
        return replace(
            facility,
            address=facility.address or result.address,
            geocoded_address=result.address,
        )

    def primary_for_type(self, facility_type: str) -> FacilityRecord | None:
        rows = self.repository.list_facilities(facility_type=facility_type, status=None)
        for row in rows:
            if row.is_primary:
                return row
        return None

    def _normalize(self, facility: FacilityRecord) -> FacilityRecord:
        return replace(
            facility,
            incident_id=self.incident_id,
            name=facility.name.strip(),
            facility_type=(facility.facility_type or "other").strip(),
            status=(facility.status or "active").strip(),
            address=facility.address.strip(),
            geocoded_address=facility.geocoded_address.strip(),
            manager_personnel_id=facility.manager_personnel_id.strip(),
            manager_name=facility.manager_name.strip(),
            contact_name=facility.contact_name.strip(),
            contact_phone=facility.contact_phone.strip(),
            notes=facility.notes.strip(),
            function_tags=self._normalize_tags(facility.function_tags),
            served_sections=self._normalize_tags(facility.served_sections),
        )

    def _validate(self, facility: FacilityRecord) -> None:
        if not self.incident_id:
            raise ValueError("No active incident selected.")
        if not facility.name.strip():
            raise ValueError("Facility name is required.")
        if facility.facility_type and facility.facility_type not in FACILITY_TYPES:
            raise ValueError(f"Unknown facility type: {facility.facility_type}")
        if facility.status and facility.status not in FACILITY_STATUSES:
            raise ValueError(f"Unknown facility status: {facility.status}")

    @staticmethod
    def _normalize_tags(values: list[str]) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []
        for value in values:
            token = value.strip()
            if not token:
                continue
            key = token.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(token)
        return normalized


__all__ = ["FacilitiesService"]
