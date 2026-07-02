"""Shared resource type assignment helpers.

This module keeps the cross-cutting "real resource -> resource type" mapping
logic in one place so personnel, vehicles, equipment, teams, and check-in can
all use the same schema and query behavior.
"""
from __future__ import annotations

from typing import Any, Iterable, Optional


READINESS_STATUSES: tuple[str, ...] = (
    "Ready",
    "Partially Ready",
    "Missing Personnel",
    "Missing Equipment",
    "Out of Service",
    "Unknown",
)


class ApiResourceAssignmentRepository:
    """ResourceAssignmentRepository backed by the SARApp API (MongoDB)."""

    def get_resource_type_name(self, resource_type_id: Optional[int]) -> str:
        if resource_type_id in (None, ""):
            return ""
        try:
            from utils.api_client import api_client
            doc = api_client.get(f"/api/resource-types/{resource_type_id}")
            return str(doc.get("planning_display_name") or doc.get("name") or "")
        except Exception:
            return ""

    def get_vehicle_resource_type(self, vehicle_id) -> Optional[int]:
        try:
            from utils.api_client import api_client
            doc = api_client.get(f"/api/master/vehicles/{vehicle_id}")
            rt = doc.get("resource_type_id")
            return int(rt) if rt is not None else None
        except Exception:
            return None

    def set_vehicle_resource_type(self, vehicle_id, resource_type_id: Optional[int]) -> None:
        try:
            from utils.api_client import api_client
            api_client.patch(f"/api/master/vehicles/{vehicle_id}", json={"resource_type_id": resource_type_id})
        except Exception:
            pass

    def get_team_resource_type(self, team_id) -> Optional[int]:
        try:
            from utils.api_client import api_client
            from utils.incident_context import get_active_incident_id
            iid = get_active_incident_id()
            if not iid:
                return None
            doc = api_client.get(f"/api/incidents/{iid}/operations/teams/{team_id}")
            rt = doc.get("resource_type_id")
            return int(rt) if rt is not None else None
        except Exception:
            return None

    def set_team_resource_type(self, team_id, resource_type_id: Optional[int]) -> None:
        try:
            from utils.api_client import api_client
            from utils.incident_context import get_active_incident_id
            iid = get_active_incident_id()
            if not iid:
                return
            api_client.patch(f"/api/incidents/{iid}/operations/teams/{team_id}", json={"resource_type_id": resource_type_id})
        except Exception:
            pass

    def set_team_readiness_status(self, team_id, readiness_status: Optional[str]) -> None:
        try:
            from utils.api_client import api_client
            from utils.incident_context import get_active_incident_id
            iid = get_active_incident_id()
            if not iid:
                return
            api_client.patch(f"/api/incidents/{iid}/operations/teams/{team_id}", json={"readiness_status": readiness_status or "Unknown"})
        except Exception:
            pass

    def get_available_resources_by_type(self, resource_type_id: int) -> dict:
        return {"personnel": [], "team": [], "vehicle": [], "equipment": []}

    def get_personnel_resource_types(self, person_record: int) -> list:
        try:
            from utils.api_client import api_client
            doc = api_client.get(f"/api/master/personnel/{person_record}")
            return doc.get("resource_types") or []
        except Exception:
            return []

    def set_personnel_resource_types(self, person_record: int, resource_type_ids, primary_resource_type_id=None, notes_by_resource_type=None) -> None:
        try:
            from utils.api_client import api_client
            api_client.patch(f"/api/master/personnel/{person_record}", json={"resource_types": list(resource_type_ids)})
        except Exception:
            pass

    def get_personnel_capabilities(self, person_record: int) -> list:
        try:
            from utils.api_client import api_client
            doc = api_client.get(f"/api/master/personnel/{person_record}")
            return doc.get("capabilities") or []
        except Exception:
            return []

    def get_equipment_resource_type(self, equipment_id) -> Optional[int]:
        try:
            from utils.api_client import api_client
            doc = api_client.get(f"/api/master/equipment/{equipment_id}")
            rt = doc.get("resource_type_id")
            return int(rt) if rt is not None else None
        except Exception:
            return None

    def set_equipment_resource_type(self, equipment_id, resource_type_id: Optional[int]) -> None:
        try:
            from utils.api_client import api_client
            api_client.patch(f"/api/master/equipment/{equipment_id}", json={"resource_type_id": resource_type_id})
        except Exception:
            pass
