"""Search Assignment Planner repository (SAR Toolkit) — proxies through SARApp API.

Architectural decision (see docs/archive/design-documents/toolkit_sar_playbook.md
and agents.md's "Operations owns the official task/assignment record and
deployment lifecycle" boundary rule):

`publish_search_task` below does NOT create a second, parallel task record.
It first calls the EXISTING Operations tasking creation API
(`modules.operations.taskings.repository.create_task`) to create the real
task, then creates a `search_task_details` record here that references the
new task's int_id. The Operations task record is checked and found to have
no extensible/metadata field suited to carrying search-specific planning
fields (track spacing, completion criteria, segment linkage, etc.) without
overloading its general `assignment`/`description` text fields, so the
two-table linked-record approach is used instead of stuffing those fields
onto the Operations task body.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from modules.sartoolkit.models.search_task import SearchTaskDetail

logger = logging.getLogger(__name__)


def _iid() -> str:
    from utils.state import AppState

    v = AppState.get_active_incident()
    if not v:
        raise RuntimeError("No active incident configured")
    return str(v)


def _client():
    from utils.api_client import api_client

    return api_client


def _base(incident_id: Optional[str] = None) -> str:
    return f"/api/incidents/{incident_id or _iid()}/search-task-details"


def list_search_task_details(incident_id: Optional[str] = None) -> list[SearchTaskDetail]:
    try:
        rows = _client().get(_base(incident_id)) or []
    except Exception:
        logger.exception("Failed to list search task details")
        return []
    return [SearchTaskDetail.from_dict(r) for r in rows]


def list_operations_tasks() -> list[dict[str, Any]]:
    """Raw Operations task documents, for joining with search_task_details in the panel."""
    from modules.operations.taskings.repository import list_tasks

    try:
        return list_tasks() or []
    except Exception:
        logger.exception("Failed to list Operations tasks")
        return []


def publish_search_task(
    *,
    title: str,
    segment_id: Optional[str],
    team_or_resource: str,
    team_leader: str,
    radio_channel: str,
    search_method: str,
    track_spacing: str,
    departure_time: Optional[str],
    due_back_time: Optional[str],
    completion_criteria: str,
    safety_notes: str,
    incident_id: Optional[str] = None,
) -> SearchTaskDetail:
    """Publish a new search task: create the real Operations task first, then
    link the search-specific fields to it. Returns the linked detail record.
    """
    from modules.operations.taskings.repository import create_task

    description_bits = [f"Search method: {search_method}"]
    if team_or_resource:
        description_bits.insert(0, f"Resource: {team_or_resource}")
    task_int_id = create_task(
        title=title or "<Search Task>",
        priority="Medium",
        status="Draft",
        description="; ".join(description_bits),
        origin_module="sartoolkit",
        origin_id=segment_id or None,
    )
    detail = SearchTaskDetail(
        task_id=task_int_id,
        segment_id=segment_id,
        search_method=search_method,
        track_spacing=track_spacing,
        completion_criteria=completion_criteria,
        safety_notes=safety_notes,
        radio_channel=radio_channel,
        team_leader=team_leader,
        departure_time=departure_time,
        due_back_time=due_back_time,
    )
    from utils.api_client import APIError

    try:
        d = _client().post(_base(incident_id), json=detail.to_payload())
        return SearchTaskDetail.from_dict(d)
    except APIError as exc:
        raise ValueError(str(exc)) from exc


def update_search_task_detail(detail: SearchTaskDetail, incident_id: Optional[str] = None) -> SearchTaskDetail:
    from utils.api_client import APIError

    try:
        d = _client().put(f"{_base(incident_id)}/{detail.id}", json=detail.to_payload())
        return SearchTaskDetail.from_dict(d)
    except APIError as exc:
        raise ValueError(str(exc)) from exc


def delete_search_task_detail(detail_id: str, incident_id: Optional[str] = None) -> bool:
    result = _client().delete(f"{_base(incident_id)}/{detail_id}")
    if isinstance(result, dict):
        return bool(result.get("ok", True))
    return True


__all__ = [
    "list_search_task_details",
    "list_operations_tasks",
    "publish_search_task",
    "update_search_task_detail",
    "delete_search_task_detail",
]
