"""Service layer for the Logistics resource status board."""
from __future__ import annotations

from typing import Any, Optional

from utils.audit import write_audit
from utils import incident_context
from utils.state import AppState

from .models import (
    PENDING_STATUSES,
    ResourceAuditEntry,
    ResourceItem,
    normalize_status,
)
from .repository import ResourceStatusRepository, new_identifier, now_local_iso


class ResourceStatusService:
    """Coordinates board reads, writes, source syncing, and audit logging."""

    def __init__(self, repository: ResourceStatusRepository | None = None) -> None:
        self.repository = repository or ResourceStatusRepository()

    def list_resources(self) -> list[ResourceItem]:
        self._ensure_active_incident_state()
        self.sync_from_incident_sources()
        return self.repository.list_resources()

    def get_resource(self, resource_status_id: str) -> Optional[ResourceItem]:
        return self.repository.get_resource(resource_status_id)

    def list_audit_entries(self, resource_status_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return self.repository.list_audit_entries(resource_status_id, limit=limit)

    def create_resource(self, payload: dict[str, Any], actor_name: Optional[str] = None) -> ResourceItem:
        self._ensure_active_incident_state()
        now = now_local_iso()
        item = ResourceItem(
            id=new_identifier(),
            resource_id=str(payload.get("resource_id") or "").strip(),
            resource_name=str(payload.get("resource_name") or "").strip(),
            resource_type=str(payload.get("resource_type") or "").strip(),
            status=normalize_status(str(payload.get("status") or "Pending")),
            eta_utc=self._normalize_optional_text(payload.get("eta_utc")),
            assigned_to=self._normalize_optional_text(payload.get("assigned_to")),
            assignment_reference=self._normalize_optional_text(payload.get("assignment_reference")),
            location=self._normalize_optional_text(payload.get("location")),
            checked_in_time=self._normalize_optional_text(payload.get("checked_in_time")),
            last_updated=now,
            notes=self._normalize_optional_text(payload.get("notes")),
            source_entity_type=self._normalize_optional_text(payload.get("source_entity_type")),
            source_record_id=self._normalize_optional_text(payload.get("source_record_id")),
            created_at=now,
            updated_at=now,
        )
        self._validate_item(item)
        self.repository.save_resource(item)
        self._write_audit(item, {}, item.to_row(), actor_name=actor_name, action="logistics.resource_status.create")
        return item

    def update_resource(
        self,
        resource_status_id: str,
        patch: dict[str, Any],
        actor_name: Optional[str] = None,
    ) -> ResourceItem:
        self._ensure_active_incident_state()
        current = self.repository.get_resource(resource_status_id)
        if current is None:
            raise ValueError(f"Unknown tracked resource: {resource_status_id}")

        next_item = ResourceItem(**current.to_row())
        for key in (
            "resource_id",
            "resource_name",
            "resource_type",
            "assigned_to",
            "assignment_reference",
            "location",
            "checked_in_time",
            "notes",
        ):
            if key in patch:
                setattr(next_item, key, self._normalize_optional_text(patch.get(key)))

        if "status" in patch:
            next_item.status = normalize_status(str(patch.get("status") or ""))
        if "eta_utc" in patch:
            next_item.eta_utc = self._normalize_optional_text(patch.get("eta_utc"))

        if next_item.status == "Checked In" and not next_item.checked_in_time:
            next_item.checked_in_time = now_local_iso()
        next_item.last_updated = now_local_iso()
        next_item.updated_at = next_item.last_updated

        self._validate_item(next_item)
        before = current.to_row()
        after = next_item.to_row()
        self.repository.save_resource(next_item)
        self._write_audit(
            next_item,
            before,
            after,
            actor_name=actor_name,
            action="logistics.resource_status.update",
        )
        return next_item

    def sync_from_incident_sources(self) -> int:
        """Create board rows for incident resources that are not tracked yet."""

        self._ensure_active_incident_state()
        created = 0
        for source in self.repository.source_rows():
            entity_type = str(source.get("entity_type") or "resource")
            record = dict(source.get("record") or {})
            identifier_column = str(source.get("identifier_column") or "id")
            source_record_id = record.get(identifier_column)
            if source_record_id in (None, ""):
                continue
            if self.repository.get_by_source(entity_type, str(source_record_id)) is not None:
                continue
            resource_payload = self._resource_payload_from_source(entity_type, record, source_record_id)
            self.create_resource(resource_payload, actor_name="System Sync")
            created += 1
        return created


    def _ensure_active_incident_state(self) -> None:
        incident_id = incident_context.get_active_incident_id()
        if incident_id and AppState.get_active_incident() != incident_id:
            AppState.set_active_incident(incident_id)

    def _resource_payload_from_source(
        self,
        entity_type: str,
        record: dict[str, Any],
        source_record_id: Any,
    ) -> dict[str, Any]:
        resource_type = {
            "personnel": "Personnel",
            "vehicle": "Vehicle",
            "equipment": "Equipment",
            "aircraft": "Aircraft",
        }.get(entity_type, entity_type.title())
        return {
            "resource_id": str(source_record_id),
            "resource_name": self._name_from_source(entity_type, record, source_record_id),
            "resource_type": resource_type,
            "status": self._status_from_source(entity_type, record),
            "assigned_to": self._assignment_from_source(entity_type, record),
            "location": self._location_from_source(record),
            "checked_in_time": self._first_value(record, "created_at", "updated_at"),
            "notes": self._first_value(record, "notes", "condition", "capabilities"),
            "source_entity_type": entity_type,
            "source_record_id": str(source_record_id),
        }

    def _validate_item(self, item: ResourceItem) -> None:
        if not item.resource_id:
            raise ValueError("Resource ID is required")
        if not item.resource_name:
            raise ValueError("Resource Name is required")
        if not item.resource_type:
            raise ValueError("Resource Type is required")
        if item.status in PENDING_STATUSES:
            # ETA is optional, but the data model must always include a place to store it.
            item.eta_utc = self._normalize_optional_text(item.eta_utc)

    def _write_audit(
        self,
        item: ResourceItem,
        before: dict[str, Any],
        after: dict[str, Any],
        *,
        actor_name: Optional[str],
        action: str,
    ) -> None:
        changes = self._diff(before, after)
        if not changes:
            return
        changed_at = now_local_iso()
        entries: list[ResourceAuditEntry] = []
        for field_name, change in changes.items():
            entries.append(
                ResourceAuditEntry(
                    id=new_identifier(),
                    resource_status_id=item.id,
                    field_name=field_name,
                    old_value=change.get("old"),
                    new_value=change.get("new"),
                    actor_name=actor_name,
                    changed_at=changed_at,
                )
            )
        self.repository.save_audit_entries(entries)
        write_audit(
            action,
            {
                "resource_status_id": item.id,
                "resource_id": item.resource_id,
                "resource_name": item.resource_name,
                "changes": changes,
            },
        )

    def _diff(self, before: dict[str, Any], after: dict[str, Any]) -> dict[str, dict[str, Optional[str]]]:
        changes: dict[str, dict[str, Optional[str]]] = {}
        for field_name, new_value in after.items():
            old_value = before.get(field_name)
            if self._normalize_optional_text(old_value) != self._normalize_optional_text(new_value):
                changes[field_name] = {
                    "old": self._normalize_optional_text(old_value),
                    "new": self._normalize_optional_text(new_value),
                }
        return changes

    def _status_from_source(self, entity_type: str, record: dict[str, Any]) -> str:
        raw_status = str(
            self._first_value(record, "status", "status_id", "ci_status", "personnel_status") or ""
        ).strip()
        if not raw_status:
            if entity_type == "personnel" and record.get("team_id"):
                return "Assigned"
            return "Checked In"

        lowered = raw_status.lower()
        if lowered in {"pending", "enroute", "en route"}:
            return normalize_status(raw_status)
        if lowered in {"checkedin", "checked in", "aticp"}:
            return "Checked In"
        if lowered in {"assigned", "deployed", "checked_out"}:
            return "Assigned"
        if lowered in {"available", "ready", "in service"}:
            return "Available"
        if lowered in {"out of service", "maintenance", "unavailable", "offduty", "off duty"}:
            return "Out of Service"
        if lowered in {"demobilized", "retired", "released", "noshow", "no show"}:
            return "Demobilized"
        return "Checked In"

    def _name_from_source(self, entity_type: str, record: dict[str, Any], source_record_id: Any) -> str:
        if entity_type == "personnel":
            return str(self._first_value(record, "name", "callsign", "id") or source_record_id)
        if entity_type == "vehicle":
            return str(
                self._first_value(
                    record,
                    "callsign",
                    "license_plate",
                    "id",
                )
                or self._join_values(record.get("year"), record.get("make"), record.get("model"))
                or source_record_id
            )
        if entity_type == "equipment":
            return str(self._first_value(record, "name", "serial_number", "id") or source_record_id)
        if entity_type == "aircraft":
            return str(self._first_value(record, "callsign", "tail_number", "id") or source_record_id)
        return str(source_record_id)

    def _assignment_from_source(self, entity_type: str, record: dict[str, Any]) -> Optional[str]:
        if entity_type == "personnel":
            return self._normalize_optional_text(self._first_value(record, "team_id", "role_on_team"))
        if entity_type in {"vehicle", "aircraft"}:
            return self._normalize_optional_text(self._first_value(record, "current_assignment", "team_id"))
        if entity_type == "equipment" and record.get("current_holder_id"):
            return f"Holder {record['current_holder_id']}"
        return None

    def _location_from_source(self, record: dict[str, Any]) -> Optional[str]:
        return self._normalize_optional_text(self._first_value(record, "location", "base_location", "home_unit"))

    @staticmethod
    def _first_value(record: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            value = record.get(key)
            if value not in (None, ""):
                return value
        return None

    @staticmethod
    def _join_values(*values: Any) -> Optional[str]:
        parts = [str(value).strip() for value in values if value not in (None, "") and str(value).strip()]
        return " ".join(parts) if parts else None

    @staticmethod
    def _normalize_optional_text(value: Any) -> Optional[str]:
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
