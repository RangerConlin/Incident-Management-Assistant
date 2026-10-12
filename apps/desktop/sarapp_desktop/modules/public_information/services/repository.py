"""API-backed repository for Public Information records.

The Public Information UI keeps using this small repository surface, while
persistence is handled by the SARApp API server and per-incident MongoDB
collections.
"""

from __future__ import annotations

from typing import Any, Optional

from modules.public_information.models.records import utc_now


class PublicInformationRepository:
    """Data access layer for the Public Information module."""

    def __init__(self, incident_id: Optional[str] = None, api_client=None):
        self.incident_id = str(incident_id or "unassigned")
        self._base = f"/api/incidents/{self.incident_id}/public-information"
        self._api_client = api_client

    @property
    def api_client(self):
        if self._api_client is not None:
            return self._api_client
        from utils.api_client import api_client

        return api_client

    def initialize_schema(self) -> None:
        """MongoDB is schemaless; indexes are managed by the shared server."""

    def list_messages(self) -> list[dict[str, Any]]:
        return self.api_client.get(f"{self._base}/messages") or []

    def get_message(self, message_id: int) -> Optional[dict[str, Any]]:
        try:
            return self.api_client.get(f"{self._base}/messages/{int(message_id)}")
        except Exception:
            return None

    def save_message(self, data: dict[str, Any], user: str = "") -> dict[str, Any]:
        payload = dict(data)
        payload["_revision_user"] = user
        return self.api_client.post(f"{self._base}/messages", json=payload) or {}

    def add_revision(self, message_id: int, data: dict[str, Any], user: str = "") -> None:
        # Revisions are created as part of save_message in the MongoDB API.
        return None

    def set_message_status(self, message_id: int, status: str, user: str = "", comment: str = "") -> dict[str, Any]:
        return self.api_client.post(
            f"{self._base}/messages/{int(message_id)}/status",
            json={"status": status, "user": user, "comment": comment},
        ) or {}

    def list_approvals(self, message_id: int) -> list[dict[str, Any]]:
        return self.api_client.get(f"{self._base}/messages/{int(message_id)}/approvals") or []

    def list_templates(self, active_only: bool = False) -> list[dict[str, Any]]:
        return self.api_client.get(
            f"{self._base}/templates",
            params={"active_only": str(active_only).lower()},
        ) or []

    def get_template(self, template_id: int) -> Optional[dict[str, Any]]:
        try:
            return self.api_client.get(f"{self._base}/templates/{int(template_id)}")
        except Exception:
            return None

    def save_template(self, data: dict[str, Any]) -> dict[str, Any]:
        return self.api_client.post(f"{self._base}/templates", json=dict(data)) or {}

    def create_response_draft_from_media(self, media_id: int, user: str = "") -> dict[str, Any]:
        return self.api_client.post(
            f"{self._base}/media/{int(media_id)}/response-draft",
            json={"user": user},
        ) or {}

    def save_record(self, table: str, data: dict[str, Any], timestamp_field: Optional[str] = None) -> dict[str, Any]:
        values = dict(data)
        if timestamp_field:
            values[timestamp_field] = utc_now()
        return self.api_client.post(f"{self._base}/records/{table}", json=values) or {}

    def list_records(self, table: str, order_by: str = "id DESC") -> list[dict[str, Any]]:
        return self.api_client.get(
            f"{self._base}/records/{table}",
            params={"order_by": order_by},
        ) or []

    def add_misinformation_timeline(self, item_id: int, event_text: str, user: str = "") -> None:
        self.api_client.post(
            f"{self._base}/misinformation/{int(item_id)}/timeline",
            json={"event_text": event_text, "user": user},
        )

    def list_misinformation_timeline(self, item_id: int) -> list[dict[str, Any]]:
        return self.api_client.get(f"{self._base}/misinformation/{int(item_id)}/timeline") or []

    def summary_counts(self) -> dict[str, int | str]:
        return self.api_client.get(f"{self._base}/summary") or {
            "Pending Approvals": 0,
            "Draft Messages": 0,
            "Published / Released Messages": 0,
            "Media Follow-Ups": 0,
            "Active Misinformation Items": 0,
            "Next Briefing / Next Update": "Not scheduled",
        }
