"""Leads repository — API-backed."""

from __future__ import annotations

from typing import Optional

from utils.api_client import api_client, APIError
from modules.intel.models.leads import Lead


class LeadsRepository:
    """CRUD operations for Intel leads via the server API."""

    def __init__(self, incident_id: str) -> None:
        self._incident_id = incident_id
        self._base = f"/api/incidents/{incident_id}/intel/leads"

    def list(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        assigned_to: Optional[str] = None,
        include_deleted: bool = False,
    ) -> list[Lead]:
        params: dict = {"include_deleted": include_deleted}
        if status:
            params["status"] = status
        if priority:
            params["priority"] = priority
        if assigned_to:
            params["assigned_to"] = assigned_to
        try:
            data = api_client.get(self._base, params=params)
            return [Lead.from_api(d) for d in (data or [])]
        except APIError:
            return []

    def get(self, lead_id: str) -> Optional[Lead]:
        try:
            data = api_client.get(f"{self._base}/{lead_id}")
            return Lead.from_api(data)
        except APIError:
            return None

    def create(self, lead: Lead) -> Optional[Lead]:
        try:
            data = api_client.post(self._base, json=lead.to_api_dict())
            return Lead.from_api(data)
        except APIError:
            return None

    def update(self, lead_id: str, updates: dict) -> Optional[Lead]:
        try:
            data = api_client.patch(f"{self._base}/{lead_id}", json=updates)
            return Lead.from_api(data)
        except APIError:
            return None

    def close(self, lead_id: str) -> bool:
        try:
            api_client.delete(f"{self._base}/{lead_id}")
            return True
        except APIError:
            return False

    def convert(self, lead_id: str, target_type: str, actor: str = "system") -> Optional[Lead]:
        """Mark the lead as converted (client still creates the target record separately)."""
        try:
            data = api_client.post(
                f"{self._base}/{lead_id}/convert",
                json={"target_type": target_type, "actor": actor},
            )
            return Lead.from_api(data)
        except APIError:
            return None
