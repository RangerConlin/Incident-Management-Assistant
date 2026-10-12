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


def _safe_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_list_of_dicts(value: Any) -> list[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[Dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            rows.append(dict(item))
    return rows


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


@dataclass(slots=True)
class InitialOverviewRecord:
    incident_id: str
    incident_mode: str = "Missing Person"
    behavior_category: str = ""
    source_info: Dict[str, Any] | None = None
    subject_info: Dict[str, Any] | None = None
    aircraft_info: Dict[str, Any] | None = None
    timeline_info: Dict[str, Any] | None = None
    primary_anchor: Dict[str, Any] | None = None
    related_locations: list[Dict[str, Any]] | None = None
    clues_environment: Dict[str, Any] | None = None
    operations_summary: Dict[str, Any] | None = None
    narrative: str = ""
    updated_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "InitialOverviewRecord":
        return cls(
            incident_id=str(row.get("incident_id", "")),
            incident_mode=str(row.get("incident_mode", "Missing Person") or "Missing Person"),
            behavior_category=str(row.get("behavior_category", "") or ""),
            source_info=_safe_dict(row.get("source_info")),
            subject_info=_safe_dict(row.get("subject_info")),
            aircraft_info=_safe_dict(row.get("aircraft_info")),
            timeline_info=_safe_dict(row.get("timeline_info")),
            primary_anchor=_safe_dict(row.get("primary_anchor")),
            related_locations=_safe_list_of_dicts(row.get("related_locations")),
            clues_environment=_safe_dict(row.get("clues_environment")),
            operations_summary=_safe_dict(row.get("operations_summary")),
            narrative=str(row.get("narrative", "") or ""),
            updated_at=_safe_str(row.get("updated_at")),
        )

    def replace(self, **changes: Any) -> "InitialOverviewRecord":
        return replace(self, **changes)
