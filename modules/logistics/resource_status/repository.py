"""API-backed repository for the Logistics resource status board."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Iterable, Optional

from .models import ResourceAuditEntry, ResourceItem


class ResourceStatusRepository:
    """Persist and query resource status board rows via the SARApp API server."""

    def _incident_id(self) -> str:
        from utils import incident_context
        from utils.state import AppState
        iid = incident_context.get_active_incident_id() or AppState.get_active_incident()
        if not iid:
            raise RuntimeError("No active incident for resource status board")
        return str(iid)

    def list_resources(self) -> list[ResourceItem]:
        from utils.api_client import api_client
        iid = self._incident_id()
        rows = api_client.get(f"/api/incidents/{iid}/logistics/resource-status")
        return [ResourceItem.from_row(r) for r in rows]

    def get_resource(self, resource_status_id: str) -> Optional[ResourceItem]:
        from utils.api_client import api_client, APIError
        iid = self._incident_id()
        try:
            row = api_client.get(f"/api/incidents/{iid}/logistics/resource-status/{resource_status_id}")
            return ResourceItem.from_row(row)
        except APIError:
            return None

    def get_by_source(self, source_entity_type: str, source_record_id: str) -> Optional[ResourceItem]:
        from utils.api_client import api_client, APIError
        iid = self._incident_id()
        try:
            row = api_client.get(
                f"/api/incidents/{iid}/logistics/resource-status/{source_record_id}/by-source",
                params={"source_entity_type": source_entity_type, "source_record_id": source_record_id},
            )
            return ResourceItem.from_row(row) if row else None
        except (APIError, Exception):
            return None

    def save_resource(self, item: ResourceItem) -> ResourceItem:
        from utils.api_client import api_client, APIError
        iid = self._incident_id()
        payload = item.to_row()
        try:
            api_client.get(f"/api/incidents/{iid}/logistics/resource-status/{item.id}")
            api_client.patch(f"/api/incidents/{iid}/logistics/resource-status/{item.id}", json=payload)
        except APIError:
            api_client.post(f"/api/incidents/{iid}/logistics/resource-status", json=payload)
        return item

    def save_audit_entries(self, entries: Iterable[ResourceAuditEntry]) -> None:
        from utils.api_client import api_client
        entries_list = list(entries)
        if not entries_list:
            return
        by_item: dict[str, list[dict]] = {}
        for entry in entries_list:
            by_item.setdefault(entry.resource_status_id, []).append(entry.to_row())
        iid = self._incident_id()
        for resource_status_id, rows in by_item.items():
            try:
                api_client.post(
                    f"/api/incidents/{iid}/logistics/resource-status/{resource_status_id}/audit",
                    json=rows,
                )
            except Exception:
                pass

    def list_audit_entries(self, resource_status_id: str, limit: int = 50) -> list[dict[str, Any]]:
        from utils.api_client import api_client, APIError
        iid = self._incident_id()
        try:
            return api_client.get(
                f"/api/incidents/{iid}/logistics/resource-status/{resource_status_id}/audit",
                params={"limit": limit},
            )
        except APIError:
            return []

    def source_rows(self) -> list[dict[str, Any]]:
        """Incident source sync deferred — checkin/vehicle/aircraft not yet migrated."""
        return []

    def ensure_schema(self, conn=None) -> None:
        pass


def new_identifier() -> str:
    return uuid.uuid4().hex


def now_local_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
