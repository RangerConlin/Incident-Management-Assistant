"""Domain models for the communications traffic log."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import json


DIRECTION_INCOMING = "Incoming"
DIRECTION_OUTGOING = "Outgoing"
DIRECTION_INTERNAL = "Internal"

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
    direction: str = DIRECTION_INCOMING
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

    def to_record(self) -> Dict[str, Any]:
        """Return a mapping ready for SQLite insertion/update."""
        payload = asdict(self)
        payload["follow_up_required"] = 1 if self.follow_up_required else 0
        payload["is_status_update"] = 1 if self.is_status_update else 0
        payload["attachments"] = json.dumps(self.attachments, ensure_ascii=False)
        # ``id`` is handled separately to avoid duplicates in INSERT payloads
        payload.pop("id", None)
        payload.pop("operator_display_name", None)
        return payload

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "CommsLogEntry":
        attachments_raw = row.get("attachments")
        if attachments_raw in (None, ""):
            attachments = []
        else:
            try:
                parsed = json.loads(attachments_raw)
            except Exception:
                parsed = []
            if isinstance(parsed, list):
                attachments = [str(p) for p in parsed]
            elif isinstance(parsed, str):
                attachments = [parsed]
            else:
                attachments = []
        return cls(
            id=row.get("id"),
            ts_utc=row.get("ts_utc") or utcnow_iso(),
            ts_local=row.get("ts_local") or localnow_iso(),
            direction=row.get("direction") or DIRECTION_INCOMING,
            priority=row.get("priority") or PRIORITY_ROUTINE,
            resource_id=row.get("resource_id"),
            resource_label=row.get("resource_label") or "",
            frequency=row.get("frequency") or "",
            band=row.get("band") or "",
            mode=row.get("mode") or "",
            from_unit=row.get("from_unit") or "",
            to_unit=row.get("to_unit") or "",
            message=row.get("message") or "",
            action_taken=row.get("action_taken") or "",
            follow_up_required=bool(row.get("follow_up_required")),
            disposition=row.get("disposition") or DISPOSITION_OPEN,
            operator_user_id=str(row.get("operator_user_id")) if row.get("operator_user_id") is not None else None,
            team_id=row.get("team_id"),
            task_id=row.get("task_id"),
            vehicle_id=row.get("vehicle_id"),
            personnel_id=row.get("personnel_id"),
            attachments=attachments,
            geotag_lat=row.get("geotag_lat"),
            geotag_lon=row.get("geotag_lon"),
            notification_level=row.get("notification_level"),
            is_status_update=bool(row.get("is_status_update")),
            created_at=row.get("created_at") or utcnow_iso(),
            updated_at=row.get("updated_at") or utcnow_iso(),
            operator_display_name=row.get("operator_display_name"),
        )


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
    directions: Optional[List[str]] = None
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
    "DIRECTION_INCOMING",
    "DIRECTION_OUTGOING",
    "DIRECTION_INTERNAL",
    "PRIORITY_ROUTINE",
    "PRIORITY_PRIORITY",
    "PRIORITY_EMERGENCY",
    "DISPOSITION_OPEN",
    "DISPOSITION_CLOSED",
]
