from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


FACILITY_TYPES: tuple[str, ...] = (
    "command_post",
    "staging",
    "base",
    "helibase",
    "helispot",
    "medical",
    "shelter",
    "supply",
    "parking",
    "other",
)

FACILITY_STATUSES: tuple[str, ...] = (
    "active",
    "planned",
    "closed",
)


@dataclass(slots=True)
class FacilityRecord:
    id: str = ""
    incident_id: str = ""
    name: str = ""
    facility_type: str = "other"
    status: str = "active"
    address: str = ""
    latitude: float | None = None
    longitude: float | None = None
    geocoded_address: str = ""
    manager_personnel_id: str = ""
    manager_name: str = ""
    contact_name: str = ""
    contact_phone: str = ""
    notes: str = ""
    function_tags: list[str] = field(default_factory=list)
    served_sections: list[str] = field(default_factory=list)
    is_primary: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "FacilityRecord":
        # Backward-compatible read: accept older capabilities/served_modules names.
        function_tags = list(data.get("function_tags") or data.get("capabilities") or [])
        served_sections = list(data.get("served_sections") or data.get("served_modules") or [])
        return cls(
            id=str(data.get("id") or ""),
            incident_id=str(data.get("incident_id") or ""),
            name=str(data.get("name") or ""),
            facility_type=str(data.get("facility_type") or "other"),
            status=str(data.get("status") or "active"),
            address=str(data.get("address") or ""),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            geocoded_address=str(data.get("geocoded_address") or ""),
            manager_personnel_id=str(data.get("manager_personnel_id") or ""),
            manager_name=str(data.get("manager_name") or ""),
            contact_name=str(data.get("contact_name") or ""),
            contact_phone=str(data.get("contact_phone") or ""),
            notes=str(data.get("notes") or ""),
            function_tags=function_tags,
            served_sections=served_sections,
            is_primary=bool(data.get("is_primary") or False),
            metadata=dict(data.get("metadata") or {}),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
        )

    def to_api_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "facility_type": self.facility_type,
            "status": self.status,
            "address": self.address,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "geocoded_address": self.geocoded_address,
            "manager_personnel_id": self.manager_personnel_id,
            "manager_name": self.manager_name,
            "contact_name": self.contact_name,
            "contact_phone": self.contact_phone,
            "notes": self.notes,
            "function_tags": list(self.function_tags),
            "served_sections": list(self.served_sections),
            "is_primary": self.is_primary,
            "metadata": dict(self.metadata),
        }

    @property
    def display_label(self) -> str:
        label = self.name or "(unnamed facility)"
        suffix = f" [{self.facility_type}]"
        if self.is_primary:
            suffix += " primary"
        return label + suffix


__all__ = ["FACILITY_STATUSES", "FACILITY_TYPES", "FacilityRecord"]
