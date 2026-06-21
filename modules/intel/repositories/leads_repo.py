"""Leads repository — API-backed."""

from __future__ import annotations

import logging
from typing import Optional

from utils.api_client import api_client, APIError
from modules.intel.models.leads import Lead

_log = logging.getLogger(__name__)


def _team_log(team_id: int, text: str) -> None:
    try:
        from modules.operations.data.repository import ics214_log_entry
        ics214_log_entry("team", team_id, text, source="auto")
    except Exception as exc:
        _log.warning("leads team ICS-214 log failed (team %s): %s", team_id, exc)


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
            result = Lead.from_api(data)
        except APIError:
            return None
        if result.assigned_team_id:
            _team_log(result.assigned_team_id,
                      f"Lead assigned: {result.display_number} — {result.title} "
                      f"(priority: {result.priority})")
        return result

    def update(self, lead_id: str, updates: dict) -> Optional[Lead]:
        prev_team_id = updates.pop("_prev_assigned_team_id", None)
        try:
            data = api_client.patch(f"{self._base}/{lead_id}", json=updates)
            result = Lead.from_api(data)
        except APIError:
            return None
        new_team_id = result.assigned_team_id
        if new_team_id and new_team_id != prev_team_id:
            _team_log(new_team_id,
                      f"Lead assigned: {result.display_number} — {result.title} "
                      f"(priority: {result.priority})")
        if prev_team_id and prev_team_id != new_team_id:
            _team_log(prev_team_id,
                      f"Lead reassigned away: {result.display_number} — {result.title}")
        return result

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
