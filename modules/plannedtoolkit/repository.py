"""Planned event toolkit repository backed by the SARApp API."""
from __future__ import annotations

from typing import Any

from utils import incident_context

from .records import (
    PlannedNotification,
    PlannedRecord,
    ScheduleTrigger,
    ScheduledItem,
    notification_from_dict,
    record_from_dict,
    schedule_from_dict,
    trigger_from_dict,
)


def _client():
    from utils.api_client import api_client
    return api_client


def _require_incident_id(incident_id: str | None = None) -> str:
    value = incident_id or incident_context.get_active_incident_id()
    if not value:
        raise RuntimeError("Active incident is not set")
    return str(value)


def _base(incident_id: str, tool: str) -> str:
    return f"/api/incidents/{incident_id}/planned/{tool}"


class PlannedToolkitRepository:
    def __init__(self, incident_id: str | None = None):
        self._incident_id = incident_id

    def _incident(self) -> str:
        return _require_incident_id(self._incident_id)

    def list_records(
        self,
        tool: str,
        *,
        status: str | None = None,
        search: str | None = None,
    ) -> list[PlannedRecord]:
        params: dict[str, str] = {}
        if status:
            params["status"] = status
        if search:
            params["search"] = search
        rows = _client().get(_base(self._incident(), tool), params=params or None) or []
        return [record_from_dict(row) for row in rows]

    def create_record(
        self,
        tool: str,
        *,
        title: str,
        summary: str = "",
        status: str | None = None,
        priority: str | None = None,
        assigned_to: str = "",
        location: str = "",
        zone: str = "",
        scheduled_at: str = "",
        due_at: str = "",
        metadata: dict[str, Any] | None = None,
        **extra: Any,
    ) -> PlannedRecord:
        payload = {
            "title": title,
            "summary": summary,
            "status": status,
            "priority": priority,
            "assigned_to": assigned_to,
            "location": location,
            "zone": zone,
            "scheduled_at": scheduled_at,
            "due_at": due_at,
            "metadata": metadata or {},
        }
        payload.update({key: value for key, value in extra.items() if value is not None})
        result = _client().post(_base(self._incident(), tool), json=payload)
        return record_from_dict(result or {})

    def update_record(self, tool: str, record_id: int, patch: dict[str, Any]) -> PlannedRecord:
        result = _client().patch(f"{_base(self._incident(), tool)}/{record_id}", json=patch)
        return record_from_dict(result or {})

    def delete_record(self, tool: str, record_id: int) -> None:
        _client().delete(f"{_base(self._incident(), tool)}/{record_id}")

    def list_schedule_items(self) -> list[ScheduledItem]:
        rows = _client().get(f"/api/incidents/{self._incident()}/planned/promotions/schedule") or []
        return [schedule_from_dict(row) for row in rows]

    def create_schedule_item(
        self,
        *,
        name: str,
        kind: str = "Milestone",
        starts_at: str = "",
        ends_at: str = "",
        notes: str = "",
        location: str = "",
        zone: str = "",
        owner: str = "",
        status: str = "",
        tags: list[str] | None = None,
    ) -> ScheduledItem:
        result = _client().post(
            f"/api/incidents/{self._incident()}/planned/promotions/schedule",
            json={
                "name": name,
                "kind": kind,
                "starts_at": starts_at,
                "ends_at": ends_at,
                "notes": notes,
                "location": location,
                "zone": zone,
                "owner": owner,
                "status": status,
                "tags": tags or [],
            },
        )
        return schedule_from_dict(result or {})

    def list_schedule_triggers(self, schedule_item_id: str | None = None) -> list[ScheduleTrigger]:
        params = {"schedule_item_id": schedule_item_id} if schedule_item_id else None
        rows = _client().get(
            f"/api/incidents/{self._incident()}/planned-meta/schedule-triggers",
            params=params,
        ) or []
        return [trigger_from_dict(row) for row in rows]

    def create_schedule_trigger(self, **payload: Any) -> ScheduleTrigger:
        result = _client().post(
            f"/api/incidents/{self._incident()}/planned-meta/schedule-triggers",
            json=dict(payload),
        )
        return trigger_from_dict(result or {})

    def update_schedule_trigger(self, record_id: int, patch: dict[str, Any]) -> ScheduleTrigger:
        result = _client().patch(
            f"/api/incidents/{self._incident()}/planned-meta/schedule-triggers/{record_id}",
            json=patch,
        )
        return trigger_from_dict(result or {})

    def delete_schedule_trigger(self, record_id: int) -> None:
        _client().delete(f"/api/incidents/{self._incident()}/planned-meta/schedule-triggers/{record_id}")

    def list_notifications(self) -> list[PlannedNotification]:
        rows = _client().get(f"/api/incidents/{self._incident()}/planned-meta/notifications") or []
        return [notification_from_dict(row) for row in rows]

    def create_notification(self, **payload: Any) -> PlannedNotification:
        result = _client().post(
            f"/api/incidents/{self._incident()}/planned-meta/notifications",
            json=dict(payload),
        )
        return notification_from_dict(result or {})

    def acknowledge_notification(
        self,
        record_id: int,
        *,
        acknowledged_by: str = "",
    ) -> PlannedNotification:
        result = _client().post(
            f"/api/incidents/{self._incident()}/planned-meta/notifications/{record_id}/acknowledge",
            json={"acknowledged_by": acknowledged_by},
        )
        return notification_from_dict(result or {})

    def dismiss_notification(self, record_id: int) -> PlannedNotification:
        result = _client().post(
            f"/api/incidents/{self._incident()}/planned-meta/notifications/{record_id}/dismiss",
            json={},
        )
        return notification_from_dict(result or {})

    def promote_quick_assignment(
        self,
        record_id: int,
        *,
        promoted_by: str = "",
    ) -> PlannedRecord:
        result = _client().post(
            f"/api/incidents/{self._incident()}/planned/quick-assignments/{record_id}/promote",
            json={"promoted_by": promoted_by},
        )
        return record_from_dict(result or {})
