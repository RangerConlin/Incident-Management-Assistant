"""Intel Log repository — API-backed (read-only from client)."""

from __future__ import annotations

from typing import Optional

from utils.api_client import api_client, APIError
from modules.intel.models.log_entry import IntelLogEntry


class IntelLogRepository:
    """Read operations for the Intel activity log."""

    def __init__(self, incident_id: str) -> None:
        self._incident_id = incident_id
        self._base = f"/api/incidents/{incident_id}/intel/log"

    def list(
        self,
        entity_type: Optional[str] = None,
        event_type: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 200,
    ) -> list[IntelLogEntry]:
        params: dict = {"limit": limit}
        if entity_type:
            params["entity_type"] = entity_type
        if event_type:
            params["event_type"] = event_type
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        try:
            data = api_client.get(self._base, params=params)
            return [IntelLogEntry.from_api(d) for d in (data or [])]
        except APIError:
            return []
