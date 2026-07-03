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
        from utils.api_client import api_client, APIError
        iid = self._incident_id()
        try:
            row = api_client.get(f"/api/incidents/{iid}/resource-status/{resource_status_id}")
            return ResourceItem.from_row(row) if row else None
        except (APIError, Exception):
            return None

    def ensure_schema(self, conn=None) -> None:
        pass


def new_identifier() -> str:
    return uuid.uuid4().hex


def now_local_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
