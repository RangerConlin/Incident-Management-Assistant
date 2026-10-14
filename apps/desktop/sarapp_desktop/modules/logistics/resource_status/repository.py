"""API-backed repository for the Logistics resource status board."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from .models import ResourceItem


class ResourceStatusRepository:
    """Thin lookup wrapper for resource_status API."""

    def _incident_id(self) -> str:
        from utils import incident_context
        iid = incident_context.get_active_incident_id()
        if not iid:
            raise RuntimeError("No active incident for resource status board")
        return str(iid)

    def get_resource(self, resource_status_id: str) -> Optional[ResourceItem]:
        row = self.get_resource_row(resource_status_id)
        return ResourceItem.from_row(row) if row else None

    def get_resource_row(self, resource_status_id: str) -> Optional[dict[str, Any]]:
        from utils.api_client import api_client, APIError
        iid = self._incident_id()
        try:
            return api_client.get(f"/api/incidents/{iid}/resource-status/{resource_status_id}") or None
        except (APIError, Exception):
            return None

    def list_resources(self) -> list[ResourceItem]:
        from utils.api_client import api_client
        iid = self._incident_id()
        rows = api_client.get(f"/api/incidents/{iid}/resource-status") or []
        return [ResourceItem.from_row(row) for row in rows]

    def ensure_schema(self, conn=None) -> None:
        pass


def new_identifier() -> str:
    return uuid.uuid4().hex


def now_local_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
