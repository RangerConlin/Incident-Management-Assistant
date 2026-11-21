"""Planned event toolkit repository backed by the SARApp API."""
from __future__ import annotations

from typing import Any

from utils import incident_context

from .records import (
    PlannedRecord,
    ScheduleTrigger,
    ScheduledItem,
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
        schedule_item_id: str | None = None,
    ) -> list[PlannedRecord]:
        params: dict[str, str] = {}
        if status:
            params["status"] = status
        if search:
            params["search"] = search
        if schedule_item_id:
            params["schedule_item_id"] = schedule_item_id
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
        time_zone: str = "",
        notes: str = "",
        location: str = "",
        zone: str = "",
        owner: str = "",
        assigned_to: str = "",
        assigned_team_id: str = "",
        assigned_person_id: str = "",
        meeting_id: str = "",
        gis_feature_id: str = "",
        quick_assignment_id: str = "",
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
                "time_zone": time_zone,
                "notes": notes,
                "location": location,
                "zone": zone,
                "owner": owner,
                "assigned_to": assigned_to,
                "assigned_team_id": assigned_team_id,
                "assigned_person_id": assigned_person_id,
                "meeting_id": meeting_id,
                "gis_feature_id": gis_feature_id,
                "quick_assignment_id": quick_assignment_id,
                "status": status,
                "tags": tags or [],
            },
        )
        return schedule_from_dict(result or {})

    def update_schedule_item(self, record_id: int, patch: dict[str, Any]) -> ScheduledItem:
        result = _client().patch(
            f"/api/incidents/{self._incident()}/planned/promotions/schedule/{record_id}",
            json=patch,
        )
        return schedule_from_dict(result or {})

    def delete_schedule_item(self, record_id: int) -> None:
        _client().delete(f"/api/incidents/{self._incident()}/planned/promotions/schedule/{record_id}")

    def _schedule_action(self, record_id: int, action: str, **payload: Any) -> ScheduledItem:
        result = _client().post(
            f"/api/incidents/{self._incident()}/planned/promotions/schedule/{record_id}/{action}",
            json={key: value for key, value in payload.items() if value is not None},
        )
        return schedule_from_dict(result or {})

    def start_schedule_item(
        self, record_id: int, *, actual_start_at: str | None = None, expected_revision: int | None = None
    ) -> ScheduledItem:
        return self._schedule_action(record_id, "start", actual_start_at=actual_start_at, expected_revision=expected_revision)

    def resume_schedule_item(
        self, record_id: int, *, actual_start_at: str | None = None, expected_revision: int | None = None
    ) -> ScheduledItem:
        return self._schedule_action(record_id, "resume", actual_start_at=actual_start_at, expected_revision=expected_revision)

    def complete_schedule_item(
        self, record_id: int, *, actual_end_at: str | None = None, expected_revision: int | None = None
    ) -> ScheduledItem:
        return self._schedule_action(record_id, "complete", actual_end_at=actual_end_at, expected_revision=expected_revision)

    def delay_schedule_item(
        self,
        record_id: int,
        *,
        delay_reason: str,
        revised_start_at: str | None = None,
        expected_revision: int | None = None,
    ) -> ScheduledItem:
        return self._schedule_action(
            record_id, "delay", delay_reason=delay_reason, revised_start_at=revised_start_at,
            expected_revision=expected_revision,
        )

    def cancel_schedule_item(
        self, record_id: int, *, cancellation_reason: str, expected_revision: int | None = None
    ) -> ScheduledItem:
        return self._schedule_action(
            record_id, "cancel", cancellation_reason=cancellation_reason, expected_revision=expected_revision
        )

    def correct_schedule_item(
        self,
        record_id: int,
        *,
        reason: str,
        status: str | None = None,
        actual_start_at: str | None = None,
        actual_end_at: str | None = None,
        expected_revision: int | None = None,
    ) -> ScheduledItem:
        return self._schedule_action(
            record_id, "correct", reason=reason, status=status,
            actual_start_at=actual_start_at, actual_end_at=actual_end_at,
            expected_revision=expected_revision,
        )

    def create_quick_assignment_from_schedule_item(self, record_id: int) -> dict[str, Any]:
        """Returns {"schedule_item": ScheduledItem, "quick_assignment": PlannedRecord}."""
        result = _client().post(
            f"/api/incidents/{self._incident()}/planned/promotions/schedule/{record_id}/create-quick-assignment",
        ) or {}
        return {
            "schedule_item": schedule_from_dict(result.get("schedule_item") or {}),
            "quick_assignment": record_from_dict(result.get("quick_assignment") or {}),
        }

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
