from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict, Optional


def _safe_str(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    return str(value)


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass(slots=True)
class HastyTaskRecord:
    id: Optional[int]
    incident_id: str
    area: str
    priority: Optional[str] = None
    notes: Optional[str] = None
    operations_task_id: Optional[int] = None
    logistics_request_id: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "HastyTaskRecord":
        return cls(
            id=row.get("id"),
            incident_id=str(row.get("incident_id")),
            area=str(row.get("area", "")),
            priority=_safe_str(row.get("priority")),
            notes=_safe_str(row.get("notes")),
            operations_task_id=_safe_int(row.get("operations_task_id")),
            logistics_request_id=_safe_str(row.get("logistics_request_id")),
            created_at=_safe_str(row.get("created_at")),
        )

    def replace(self, **changes: Any) -> "HastyTaskRecord":
        return replace(self, **changes)


@dataclass(slots=True)
class ReflexActionRecord:
    id: Optional[int]
    incident_id: str
    trigger: str
    action: Optional[str] = None
    communications_alert_id: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "ReflexActionRecord":
        return cls(
            id=row.get("id"),
            incident_id=str(row.get("incident_id")),
            trigger=str(row.get("trigger", "")),
            action=_safe_str(row.get("action")),
            communications_alert_id=_safe_str(row.get("communications_alert_id")),
            created_at=_safe_str(row.get("created_at")),
        )

    def replace(self, **changes: Any) -> "ReflexActionRecord":
        return replace(self, **changes)
