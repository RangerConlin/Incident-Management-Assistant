"""Domain models for the communications traffic log."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

PRIORITY_ROUTINE = "Routine"
PRIORITY_PRIORITY = "Priority"
PRIORITY_EMERGENCY = "Emergency"

DISPOSITION_OPEN = "Open"
DISPOSITION_CLOSED = "Closed"


def utcnow_iso() -> str:
    """Return the current UTC timestamp as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def localnow_iso() -> str:
    """Return the current local timestamp as ISO 8601 string."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass(slots=True)
class CommsLogEntry:
    """Representation of a communications traffic log entry."""

    ts_utc: str = field(default_factory=utcnow_iso)
    ts_local: str = field(default_factory=localnow_iso)
    priority: str = PRIORITY_ROUTINE
    resource_id: Optional[int] = None
    resource_label: str = ""
    frequency: str = ""
    band: str = ""
    mode: str = ""
    from_unit: str = ""
    to_unit: str = ""
    message: str = ""
    action_taken: str = ""
    follow_up_required: bool = False
    disposition: str = DISPOSITION_OPEN
    operator_user_id: Optional[str] = None
    team_id: Optional[int] = None
    task_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    personnel_id: Optional[int] = None
    attachments: List[str] = field(default_factory=list)
    geotag_lat: Optional[float] = None
    geotag_lon: Optional[float] = None
    notification_level: Optional[str] = None
    is_status_update: bool = False
    created_at: str = field(default_factory=utcnow_iso)
    updated_at: str = field(default_factory=utcnow_iso)
    operator_display_name: Optional[str] = None
    id: Optional[int] = None

@dataclass(slots=True)
class CommsLogAuditEntry:
    """Audit entry for a communications record."""

    comms_log_id: int
    action: str
    changed_by: Optional[str]
    change_json: Dict[str, Any]
    changed_at: str = field(default_factory=utcnow_iso)
    id: Optional[int] = None


@dataclass(slots=True)
class CommsLogFilterPreset:
    """Persisted user filter preset."""

    name: str
    filters: Dict[str, Any]
    user_id: str
    created_at: str = field(default_factory=utcnow_iso)
    updated_at: str = field(default_factory=utcnow_iso)
    id: Optional[int] = None


@dataclass(slots=True)
class CommsLogQuery:
    """Filter definition used for querying the log table."""

    start_ts_utc: Optional[str] = None
    end_ts_utc: Optional[str] = None
    priorities: Optional[List[str]] = None
    resource_ids: Optional[List[int]] = None
    resource_labels: Optional[List[str]] = None
    unit_like: Optional[str] = None
    operator_ids: Optional[List[str]] = None
    dispositions: Optional[List[str]] = None
    has_attachments: Optional[bool] = None
    text_search: Optional[str] = None
    notification_levels: Optional[List[str]] = None
    is_status_update: Optional[bool] = None
    follow_up_required: Optional[bool] = None
    task_ids: Optional[List[int]] = None
    team_ids: Optional[List[int]] = None
    vehicle_ids: Optional[List[int]] = None
    personnel_ids: Optional[List[int]] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    order_by: str = "ts_utc"
    order_desc: bool = True


__all__ = [
    "CommsLogEntry",
    "CommsLogAuditEntry",
    "CommsLogFilterPreset",
    "CommsLogQuery",
    "utcnow_iso",
    "localnow_iso",
    "PRIORITY_ROUTINE",
    "PRIORITY_PRIORITY",
    "PRIORITY_EMERGENCY",
    "DISPOSITION_OPEN",
    "DISPOSITION_CLOSED",
]
