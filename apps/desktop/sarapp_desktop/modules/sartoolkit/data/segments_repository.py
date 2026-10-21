"""Search Segment Manager repository — proxies through SARApp API (MongoDB backend).

Mirrors the style of modules/planning/operational_periods/repository.py: all
calls go through utils/api_client.py, never direct DB access, per agents.md.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from modules.sartoolkit.models.segment import SearchSegment

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
    return f"/api/incidents/{incident_id or _iid()}/search-segments"


def list_segments(incident_id: Optional[str] = None) -> list[SearchSegment]:
    try:
        rows = _client().get(_base(incident_id)) or []
    except Exception:
        logger.exception("Failed to list search segments")
        return []
    return [SearchSegment.from_dict(r) for r in rows]


def get_segment(segment_id: str, incident_id: Optional[str] = None) -> SearchSegment:
    d = _client().get(f"{_base(incident_id)}/{segment_id}")
    return SearchSegment.from_dict(d)


def create_segment(segment: SearchSegment, incident_id: Optional[str] = None) -> SearchSegment:
    from utils.api_client import APIError

    try:
        d = _client().post(_base(incident_id), json=segment.to_payload())
        return SearchSegment.from_dict(d)
    except APIError as exc:
        raise ValueError(str(exc)) from exc


def update_segment(segment: SearchSegment, incident_id: Optional[str] = None) -> SearchSegment:
    from utils.api_client import APIError

    try:
        d = _client().put(f"{_base(incident_id)}/{segment.segment_id}", json=segment.to_payload())
        return SearchSegment.from_dict(d)
    except APIError as exc:
        raise ValueError(str(exc)) from exc


def delete_segment(segment_id: str, incident_id: Optional[str] = None) -> bool:
    result = _client().delete(f"{_base(incident_id)}/{segment_id}")
    if isinstance(result, dict):
        return bool(result.get("ok", True))
    return True


def auto_create_grid(params: dict[str, Any], incident_id: Optional[str] = None) -> list[SearchSegment]:
    from utils.api_client import APIError

    try:
        rows = _client().post(f"{_base(incident_id)}/auto-create-grid", json=params) or []
        return [SearchSegment.from_dict(r) for r in rows]
    except APIError as exc:
        raise ValueError(str(exc)) from exc


__all__ = [
    "list_segments",
    "get_segment",
    "create_segment",
    "update_segment",
    "delete_segment",
    "auto_create_grid",
]
