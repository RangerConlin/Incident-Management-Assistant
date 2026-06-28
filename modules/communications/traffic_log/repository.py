"""Persistence layer for the communications traffic log.

Backed entirely by the SARApp API / MongoDB - see ``ApiCommsLogRepository``
below. There used to also be a SQLite-backed ``CommsLogRepository`` here;
it was removed once every live caller (``services.py``, the
``ui/widgets/data_providers.py`` quick-log shortcut) moved onto the Mongo
endpoints in ``data/db/sarapp_db/api/routers/communications.py``.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .models import (
    CommsLogAuditEntry,
    CommsLogEntry,
    CommsLogFilterPreset,
    CommsLogQuery,
    DISPOSITION_OPEN,
)


class ApiCommsLogRepository:
    """CommsLogRepository backed by the SARApp API (MongoDB)."""

    def __init__(self, incident_id: Optional[str] = None, master_repo=None):
        from utils.state import AppState
        incident = incident_id or AppState.get_active_incident()
        if not incident:
            raise RuntimeError("No active incident configured")
        self.incident_id = str(incident)
        self._base = f"/api/incidents/{self.incident_id}/comms-log"

    def _entry_from_response(self, data: dict) -> CommsLogEntry:
        if data.get("attachments") and isinstance(data["attachments"], str):
            try:
                data["attachments"] = json.loads(data["attachments"])
            except Exception:
                data["attachments"] = []
        return CommsLogEntry(
            id=data.get("id"),
            ts_utc=data.get("ts_utc", ""),
            ts_local=data.get("ts_local", ""),
            priority=data.get("priority", "Routine"),
            resource_id=data.get("resource_id"),
            resource_label=data.get("resource_label", ""),
            frequency=data.get("frequency", ""),
            band=data.get("band", ""),
            mode=data.get("mode", ""),
            from_unit=data.get("from_unit", ""),
            to_unit=data.get("to_unit", ""),
            message=data.get("message", ""),
            action_taken=data.get("action_taken", ""),
            follow_up_required=bool(data.get("follow_up_required", False)),
            disposition=data.get("disposition", "Open"),
            operator_user_id=data.get("operator_user_id"),
            operator_display_name=data.get("operator_display_name"),
            team_id=data.get("team_id"),
            task_id=data.get("task_id"),
            vehicle_id=data.get("vehicle_id"),
            personnel_id=data.get("personnel_id"),
            attachments=data.get("attachments") or [],
            geotag_lat=data.get("geotag_lat"),
            geotag_lon=data.get("geotag_lon"),
            notification_level=data.get("notification_level"),
            is_status_update=bool(data.get("is_status_update", False)),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )

    def add_entry(self, entry: CommsLogEntry) -> CommsLogEntry:
        from utils.api_client import api_client
        from dataclasses import asdict
        payload = asdict(entry)
        payload.pop("id", None)
        result = api_client.post(self._base, json=payload)
        saved = self._entry_from_response(result)
        if saved.team_id:
            try:
                from modules.operations.data.repository import ics214_log_entry
                direction = entry.direction or ""
                priority = entry.priority or "Routine"
                text = entry.message or ""
                parts = []
                if direction:
                    parts.append(direction)
                if priority and priority != "Routine":
                    parts.append(priority)
                if entry.from_unit:
                    parts.append(f"from {entry.from_unit}")
                if entry.to_unit:
                    parts.append(f"to {entry.to_unit}")
                prefix = " / ".join(parts)
                log_text = f"[Comms] {prefix}: {text}" if prefix else f"[Comms] {text}"
                ics214_log_entry("team", int(saved.team_id), log_text[:200], source="auto")
            except Exception:
                pass
            # Auto-flag the team as needing assistance when a Priority or
            # Emergency entry is logged against it.
            try:
                priority = str(saved.priority or entry.priority or "Routine").strip()
                if priority in ("Priority", "Emergency"):
                    from modules.operations.teams.data import repository as team_repo
                    team_repo.set_team_needs_attention(int(saved.team_id), True)
            except Exception:
                pass
        return saved

    def get_entry(self, entry_id: int) -> CommsLogEntry:
        from utils.api_client import api_client
        result = api_client.get(f"{self._base}/{entry_id}")
        return self._entry_from_response(result)

    def list_entries(self, query: Optional[CommsLogQuery] = None) -> List[CommsLogEntry]:
        from utils.api_client import api_client
        params: Dict[str, Any] = {}
        if query:
            if query.start_ts_utc:
                params["start_ts_utc"] = query.start_ts_utc
            if query.end_ts_utc:
                params["end_ts_utc"] = query.end_ts_utc
            if query.priorities:
                params["priorities"] = ",".join(query.priorities)
            if query.dispositions:
                params["dispositions"] = ",".join(query.dispositions)
            if query.is_status_update is not None:
                params["is_status_update"] = str(query.is_status_update).lower()
            if query.follow_up_required is not None:
                params["follow_up_required"] = str(query.follow_up_required).lower()
            if query.text_search:
                params["text_search"] = query.text_search
            if query.order_by:
                params["order_by"] = query.order_by
            params["order_desc"] = str(query.order_desc).lower()
            if query.limit is not None:
                params["limit"] = str(query.limit)
            if query.offset:
                params["offset"] = str(query.offset)
        results = api_client.get(self._base, params=params or None)
        return [self._entry_from_response(r) for r in results]

    def update_entry(self, entry_id: int, patch: Dict[str, Any]) -> CommsLogEntry:
        from utils.api_client import api_client
        result = api_client.patch(f"{self._base}/{entry_id}", json=patch)
        return self._entry_from_response(result)

    def delete_entry(self, entry_id: int) -> None:
        from utils.api_client import api_client
        api_client.delete(f"{self._base}/{entry_id}")

    def list_audit_entries(self, entry_id: int) -> List[CommsLogAuditEntry]:
        from utils.api_client import api_client
        results = api_client.get(f"{self._base}/{entry_id}/audit")
        audit = []
        for r in results:
            audit.append(CommsLogAuditEntry(
                id=r.get("id"),
                comms_log_id=entry_id,
                action=r.get("action", ""),
                changed_by=r.get("changed_by"),
                changed_at=r.get("changed_at"),
                change_json=r.get("change_json") or {},
            ))
        return audit

    def list_contact_entities(self) -> List[Dict[str, Any]]:
        from utils.api_client import api_client
        try:
            return api_client.get(f"{self._base}/contacts")
        except Exception:
            return []

    def list_filter_presets(self, user_id: Optional[str] = None) -> List[CommsLogFilterPreset]:
        from utils.api_client import api_client
        from utils.state import AppState
        user = user_id or AppState.get_active_user_id()
        if not user:
            return []
        results = api_client.get(
            f"/api/incidents/{self.incident_id}/comms-log-filters",
            params={"user_id": str(user)},
        )
        return [
            CommsLogFilterPreset(
                id=r.get("preset_id"),
                name=r.get("name", ""),
                user_id=r.get("user_id", ""),
                filters=r.get("filters") or {},
                created_at=r.get("created_at"),
                updated_at=r.get("updated_at"),
            )
            for r in results
        ]

    def save_filter_preset(
        self,
        name: str,
        filters: Dict[str, Any],
        *,
        preset_id: Optional[int] = None,
        user_id: Optional[str] = None,
    ) -> CommsLogFilterPreset:
        from utils.api_client import api_client
        from utils.state import AppState
        user = user_id or AppState.get_active_user_id()
        if not user:
            raise RuntimeError("Active user is required to save presets")
        result = api_client.post(
            f"/api/incidents/{self.incident_id}/comms-log-filters",
            json={"name": name, "filters": filters, "preset_id": preset_id, "user_id": str(user)},
        )
        return CommsLogFilterPreset(
            id=result.get("preset_id"),
            name=result.get("name", name),
            user_id=result.get("user_id", str(user)),
            filters=result.get("filters") or filters,
            created_at=result.get("created_at"),
            updated_at=result.get("updated_at"),
        )

    def delete_filter_preset(self, preset_id: int, *, user_id: Optional[str] = None) -> None:
        from utils.api_client import api_client
        from utils.state import AppState
        user = user_id or AppState.get_active_user_id()
        if not user:
            raise RuntimeError("Active user is required")
        api_client.delete(
            f"/api/incidents/{self.incident_id}/comms-log-filters/{preset_id}",
            params={"user_id": str(user)},
        )

    def mark_disposition(self, entry_id: int, disposition: str) -> CommsLogEntry:
        return self.update_entry(entry_id, {"disposition": disposition or DISPOSITION_OPEN})

    def mark_follow_up(self, entry_id: int, required: bool) -> CommsLogEntry:
        return self.update_entry(entry_id, {"follow_up_required": required})

    def mark_status_update(self, entry_id: int, value: bool) -> CommsLogEntry:
        return self.update_entry(entry_id, {"is_status_update": value})


__all__ = ["ApiCommsLogRepository"]
