"""Initial response repository — MongoDB-backed via SARApp API."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from utils import incident_context

from .models import HastyTaskRecord, InitialOverviewRecord, ReflexActionRecord


def _client():
    from utils.api_client import api_client
    return api_client


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _require_incident_id() -> str:
    incident_id = incident_context.get_active_incident_id()
    if not incident_id:
        raise RuntimeError("Active incident is not set")
    return incident_id


def _base(incident_id: str) -> str:
    return f"/api/incidents/{incident_id}/initialresponse"


def _record_from_dict(d: dict) -> HastyTaskRecord:
    return HastyTaskRecord(
        id=d.get("id"),
        incident_id=str(d.get("incident_id", "")),
        area=str(d.get("area", "")),
        priority=d.get("priority"),
        notes=d.get("notes"),
        operations_task_id=d.get("operations_task_id"),
        logistics_request_id=d.get("logistics_request_id"),
        created_at=d.get("created_at"),
    )


def _reflex_from_dict(d: dict) -> ReflexActionRecord:
    return ReflexActionRecord(
        id=d.get("id"),
        incident_id=str(d.get("incident_id", "")),
        trigger=str(d.get("trigger", "")),
        action=d.get("action"),
        communications_alert_id=d.get("communications_alert_id"),
        created_at=d.get("created_at"),
    )


def _overview_from_dict(d: dict) -> InitialOverviewRecord:
    return InitialOverviewRecord.from_row(d)


def get_initial_overview(incident_id: str | None = None) -> InitialOverviewRecord:
    iid = incident_id or _require_incident_id()
    payload = _client().get(f"{_base(iid)}/overview")
    return _overview_from_dict(payload)


def save_initial_overview(record: InitialOverviewRecord, incident_id: str | None = None) -> InitialOverviewRecord:
    iid = incident_id or record.incident_id or _require_incident_id()
    payload = _client().put(
        f"{_base(iid)}/overview",
        json={
            "incident_mode": record.incident_mode,
            "behavior_category": record.behavior_category,
            "source_info": record.source_info or {},
            "subject_info": record.subject_info or {},
            "aircraft_info": record.aircraft_info or {},
            "timeline_info": record.timeline_info or {},
            "primary_anchor": record.primary_anchor or {},
            "related_locations": record.related_locations or [],
            "clues_environment": record.clues_environment or {},
            "operations_summary": record.operations_summary or {},
            "narrative": record.narrative or "",
        },
    )
    return _overview_from_dict(payload)


# ---------------------------------------------------------------------------
# Hasty tasks
# ---------------------------------------------------------------------------

def add_hasty_task(record: HastyTaskRecord) -> HastyTaskRecord:
    incident_id = record.incident_id or _require_incident_id()
    result = _client().post(f"{_base(incident_id)}/hasty", json={
        "incident_id": incident_id,
        "area": record.area,
        "priority": record.priority,
        "notes": record.notes,
        "operations_task_id": record.operations_task_id,
        "logistics_request_id": record.logistics_request_id,
    })
    return _record_from_dict(result)


def list_hasty_tasks(incident_id: str | None = None) -> List[HastyTaskRecord]:
    iid = incident_id or _require_incident_id()
    rows = _client().get(f"{_base(iid)}/hasty")
    return [_record_from_dict(r) for r in rows]


def update_hasty_task_task_id(record_id: int, *, operations_task_id: int, incident_id: str | None = None) -> None:
    iid = incident_id or _require_incident_id()
    _client().patch(f"{_base(iid)}/hasty/{record_id}", json={"operations_task_id": operations_task_id})


def update_hasty_task_logistics(record_id: int, *, logistics_request_id: str, incident_id: str | None = None) -> None:
    iid = incident_id or _require_incident_id()
    _client().patch(f"{_base(iid)}/hasty/{record_id}", json={"logistics_request_id": logistics_request_id})


# ---------------------------------------------------------------------------
# Reflex actions
# ---------------------------------------------------------------------------

def add_reflex_action(record: ReflexActionRecord) -> ReflexActionRecord:
    incident_id = record.incident_id or _require_incident_id()
    result = _client().post(f"{_base(incident_id)}/reflex", json={
        "incident_id": incident_id,
        "trigger": record.trigger,
        "action": record.action,
        "communications_alert_id": record.communications_alert_id,
    })
    return _reflex_from_dict(result)


def list_reflex_actions(incident_id: str | None = None) -> List[ReflexActionRecord]:
    iid = incident_id or _require_incident_id()
    rows = _client().get(f"{_base(iid)}/reflex")
    return [_reflex_from_dict(r) for r in rows]


def update_reflex_notification(record_id: int, *, communications_alert_id: str, incident_id: str | None = None) -> None:
    iid = incident_id or _require_incident_id()
    _client().patch(
        f"{_base(iid)}/reflex/{record_id}/notification",
        json={"communications_alert_id": communications_alert_id},
    )
