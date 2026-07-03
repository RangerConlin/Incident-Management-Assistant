"""Service layer for the Logistics resource status board."""
from __future__ import annotations

from typing import Any, Optional

from utils.audit import write_audit
from utils import incident_context

from .models import ResourceItem, normalize_status
from .repository import ResourceStatusRepository, new_identifier, now_local_iso


class ResourceStatusService:
    """Coordinates board reads and writes for the resource_status collection."""

    def __init__(self, repository: ResourceStatusRepository | None = None) -> None:
        self.repository = repository or ResourceStatusRepository()

    def list_resources(self) -> list[ResourceItem]:
        """Return current rows from the resource_status desk (no direct API call)."""
        from modules.statusboards.resource_status_desk import get_resource_status_desk
        self._ensure_active_incident_state()
        items = []
        for row in get_resource_status_desk().resource_rows():
            try:
                items.append(ResourceItem.from_row(row))
            except Exception:
                pass
        return items

    def get_resource(self, resource_status_id: str) -> Optional[ResourceItem]:
        return self.repository.get_resource(resource_status_id)

    def list_audit_entries(self, resource_status_id: str, limit: int = 50) -> list[dict[str, Any]]:
        # Status history is embedded in resource_status.status_log on the server.
        return []

    def create_resource(self, payload: dict[str, Any], actor_name: Optional[str] = None) -> ResourceItem:
        from utils.api_client import api_client
        self._ensure_active_incident_state()
        iid = self._active_incident_id()

        resource_name = str(payload.get("resource_name") or "").strip()
        resource_type = str(payload.get("resource_type") or "").strip()
        if not resource_name:
            raise ValueError("Resource Name is required")
        if not resource_type:
            raise ValueError("Resource Type is required")

        status = normalize_status(str(payload.get("status") or "Pending"))
        entity_type = self._text(payload.get("source_entity_type")) or "manual"
        record_id: Any = self._text(payload.get("source_record_id")) or payload.get("resource_id") or new_identifier()

        post_body: dict[str, Any] = {
            "entity_type": entity_type,
            "record_id": record_id,
            "resource_name": resource_name,
            "resource_type": resource_type,
            "status": status,
            "changed_by": actor_name or "Desktop Logistics",
        }
        for key in ("eta_utc", "assigned_to", "assignment_reference", "location",
                    "destination_facility_id", "checkin_facility_id", "notes"):
            val = self._text(payload.get(key))
            if val is not None:
                post_body[key] = val

        result = api_client.post(f"/api/incidents/{iid}/resource-status", json=post_body)

        write_audit("logistics.resource_status.create", {
            "resource_name": resource_name,
            "resource_type": resource_type,
            "status": status,
            "actor": actor_name,
        })

        item_id = str(result.get("id") or result.get("_id") or "")
        row: dict[str, Any] = {
            "id": item_id,
            "resource_id": str(payload.get("resource_id") or record_id),
            "resource_name": resource_name,
            "resource_type": resource_type,
            "status": status,
            "source_entity_type": entity_type,
            "source_record_id": str(record_id),
        }
        for key in ("eta_utc", "assigned_to", "assignment_reference", "location",
                    "destination_facility_id", "checkin_facility_id", "notes"):
            if key in post_body:
                row[key] = post_body[key]
        return ResourceItem.from_row(row)

    def update_resource(
        self,
        resource_status_id: str,
        patch: dict[str, Any],
        actor_name: Optional[str] = None,
    ) -> ResourceItem:
        from utils.api_client import api_client
        self._ensure_active_incident_state()
        iid = self._active_incident_id()

        current = self.repository.get_resource(resource_status_id)
        if current is None:
            raise ValueError(f"Unknown tracked resource: {resource_status_id}")

        new_status = self._text(patch.get("status"))

        field_patch: dict[str, Any] = {}
        for key in ("resource_id", "resource_name", "resource_type", "assigned_to",
                    "assignment_reference", "location", "destination_facility_id",
                    "checkin_facility_id", "checked_in_time", "notes", "eta_utc"):
            if key in patch:
                field_patch[key] = self._text(patch[key])
        if field_patch:
            api_client.patch(
                f"/api/incidents/{iid}/resource-status/{resource_status_id}",
                json=field_patch,
            )

        if new_status and new_status != current.status:
            api_client.patch(
                f"/api/incidents/{iid}/resource-status/{resource_status_id}/status",
                json={"status": new_status, "changed_by": actor_name or "Desktop Logistics"},
            )

        current_row = current.to_row()
        next_row = {**current_row, **field_patch}
        if new_status:
            next_row["status"] = new_status
        changes = self._diff(current_row, next_row)
        if changes:
            write_audit("logistics.resource_status.update", {
                "resource_status_id": resource_status_id,
                "resource_name": current.resource_name,
                "changes": changes,
                "actor": actor_name,
            })

        return ResourceItem.from_row(next_row)

    # ------------------------------------------------------------------

    def _active_incident_id(self) -> str:
        iid = incident_context.get_active_incident_id()
        if not iid:
            raise RuntimeError("No active incident for resource status board")
        return str(iid)

    def _ensure_active_incident_state(self) -> None:
        from utils.state import AppState
        incident_id = incident_context.get_active_incident_id()
        if incident_id and AppState.get_active_incident() != incident_id:
            AppState.set_active_incident(incident_id)

    def _diff(
        self, before: dict[str, Any], after: dict[str, Any]
    ) -> dict[str, dict[str, Optional[str]]]:
        changes: dict[str, dict[str, Optional[str]]] = {}
        for field_name, new_value in after.items():
            old_value = before.get(field_name)
            if self._text(old_value) != self._text(new_value):
                changes[field_name] = {"old": self._text(old_value), "new": self._text(new_value)}
        return changes

    @staticmethod
    def _text(value: Any) -> Optional[str]:
        if value in (None, ""):
            return None
        text = str(value).strip()
        return text or None


_SERVICE: ResourceStatusService | None = None


def get_service() -> ResourceStatusService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = ResourceStatusService()
    return _SERVICE


__all__ = [
    "ResourceStatusService",
    "get_service",
]
