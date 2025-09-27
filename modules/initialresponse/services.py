from __future__ import annotations

from typing import List, Optional

from .models import (
    HastyTaskCreate,
    HastyTaskRead,
    HastyTaskRecord,
    ReflexActionCreate,
    ReflexActionRead,
    ReflexActionRecord,
)
from .repository import (
    add_hasty_task,
    add_reflex_action,
    list_hasty_tasks,
    list_reflex_actions,
    update_hasty_task_logistics,
    update_hasty_task_task_id,
    update_reflex_notification,
)


# ---------------------------------------------------------------------------
# Query helpers

def list_hasty_task_entries() -> List[HastyTaskRead]:
    rows: List[HastyTaskRead] = []
    for record in list_hasty_tasks():
        rows.append(
            HastyTaskRead(
                id=record.id or 0,
                area=record.area,
                priority=record.priority,
                notes=record.notes,
                operations_task_id=record.operations_task_id,
                logistics_request_id=record.logistics_request_id,
                created_at=record.created_at,
            )
        )
    return rows


def list_reflex_action_entries() -> List[ReflexActionRead]:
    rows: List[ReflexActionRead] = []
    for record in list_reflex_actions():
        rows.append(
            ReflexActionRead(
                id=record.id or 0,
                trigger=record.trigger,
                action=record.action,
                communications_alert_id=record.communications_alert_id,
                created_at=record.created_at,
            )
        )
    return rows


# ---------------------------------------------------------------------------
# Creation helpers

def create_hasty_task(data: HastyTaskCreate) -> HastyTaskRead:
    record = HastyTaskRecord(
        id=None,
        incident_id="",
        area=data.area,
        priority=data.priority,
        notes=data.notes,
    )
    saved = add_hasty_task(record)

    task_id: Optional[int] = None
    if data.create_task:
        task_id = _create_operations_task(saved)
        if task_id and saved.id:
            update_hasty_task_task_id(
                saved.id,
                operations_task_id=task_id,
                incident_id=saved.incident_id,
            )
            saved = saved.replace(operations_task_id=task_id)

    should_request_logistics = data.request_logistics
    if saved.priority:
        key = saved.priority.strip().lower()
        if key in {"high", "critical"}:
            should_request_logistics = True
    logistics_id: Optional[str] = None
    if should_request_logistics:
        logistics_id = _create_logistics_request(saved)
        if logistics_id and saved.id:
            update_hasty_task_logistics(
                saved.id,
                logistics_request_id=logistics_id,
                incident_id=saved.incident_id,
            )
            saved = saved.replace(logistics_request_id=logistics_id)

    return HastyTaskRead(
        id=saved.id or 0,
        area=saved.area,
        priority=saved.priority,
        notes=saved.notes,
        operations_task_id=saved.operations_task_id,
        logistics_request_id=saved.logistics_request_id,
        created_at=saved.created_at,
    )


def create_reflex_action(data: ReflexActionCreate) -> ReflexActionRead:
    record = ReflexActionRecord(
        id=None,
        incident_id="",
        trigger=data.trigger,
        action=data.action,
    )
    saved = add_reflex_action(record)

    alert_id: Optional[str] = None
    if data.notify:
        alert_id = _emit_notification(
            title="Reflex tasking ready",
            message=f"Trigger: {saved.trigger}",
            severity="warning",
            entity_type="initial_reflex",
            entity_id=str(saved.id) if saved.id else None,
        )
        if alert_id and saved.id:
            update_reflex_notification(
                saved.id,
                communications_alert_id=alert_id,
                incident_id=saved.incident_id,
            )
            saved = saved.replace(communications_alert_id=alert_id)

    return ReflexActionRead(
        id=saved.id or 0,
        trigger=saved.trigger,
        action=saved.action,
        communications_alert_id=saved.communications_alert_id,
        created_at=saved.created_at,
    )


# ---------------------------------------------------------------------------
# Integrations

def _create_operations_task(record: HastyTaskRecord) -> Optional[int]:
    try:
        from modules.operations.taskings.repository import create_task, update_task_header

        priority_map = {"low": 1, "medium": 2, "moderate": 2, "high": 3, "critical": 4}
        priority_key = (record.priority or "").strip().lower()
        numeric_priority = priority_map.get(priority_key, 2)
        title = f"Hasty sweep — {record.area}"
        task_id = create_task(title=title, priority=numeric_priority, status="Planned")
        update_task_header(
            task_id,
            {
                "location": record.area,
                "assignment": "Initial Response Team",
                "task_type": "Hasty Search",
                "priority": numeric_priority,
                "notes": record.notes or "",
            },
        )
        return task_id
    except Exception as exc:  # pragma: no cover - best effort integration
        print(f"[InitialResponse] failed to create operations task: {exc}")
        return None


def _create_logistics_request(record: HastyTaskRecord) -> Optional[str]:
    try:
        from pathlib import Path

        from modules.logistics.resource_requests.api.service import ResourceRequestService
        from utils import incident_context

        incident_id = record.incident_id or incident_context.get_active_incident_id()
        if not incident_id:
            raise RuntimeError("incident id unavailable for logistics request")
        db_path = Path(incident_context.get_active_incident_db_path())
        service = ResourceRequestService(str(incident_id), db_path)

        priority_key = (record.priority or "").strip().lower()
        priority = "MEDIUM"
        if priority_key in {"high", "critical"}:
            priority = "HIGH"
        header = {
            "title": f"Initial sweep support for {record.area}",
            "requesting_section": "Operations",
            "priority": priority,
            "status": "SUBMITTED",
            "justification": record.notes or "Requesting initial response support",
        }
        items = [
            {
                "kind": "SUPPLY",
                "description": "Initial response sweep kit",
                "quantity": 1,
                "unit": "Kit",
            }
        ]
        return service.create_request(header, items)
    except Exception as exc:  # pragma: no cover - best effort integration
        print(f"[InitialResponse] failed to create logistics request: {exc}")
        return None


def _emit_notification(
    *,
    title: str,
    message: str,
    severity: str,
    entity_type: Optional[str],
    entity_id: Optional[str],
) -> Optional[str]:
    try:
        from notifications.models.notification import Notification
        from notifications.services.notifier import Notifier

        note = Notification(
            title=title,
            message=message,
            severity=severity,  # type: ignore[arg-type]
            source="Initial Response Toolkit",
            entity_type=entity_type,
            entity_id=entity_id,
        )
        Notifier.instance().notify(note)
        return entity_id
    except Exception as exc:  # pragma: no cover - optional notifier
        print(f"[InitialResponse] failed to emit notification: {exc}")
        return None


__all__ = [
    "list_hasty_task_entries",
    "list_reflex_action_entries",
    "create_hasty_task",
    "create_reflex_action",
]
