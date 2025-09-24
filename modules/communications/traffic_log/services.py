"""Service layer providing business logic for the communications log."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from modules.communications.models.master_repo import MasterRepository
from utils.state import AppState

from .exporters import csv_exporter, pdf_exporter
from .models import (
    CommsLogEntry,
    CommsLogFilterPreset,
    CommsLogQuery,
    PRIORITY_EMERGENCY,
    PRIORITY_PRIORITY,
    PRIORITY_ROUTINE,
)
from .repository import CommsLogRepository

logger = logging.getLogger(__name__)


class CommsLogService:
    """High-level API consumed by widgets and bridges."""

    def __init__(
        self,
        incident_id: Optional[str] = None,
        *,
        repository: Optional[CommsLogRepository] = None,
        master_repo: Optional[MasterRepository] = None,
    ) -> None:
        self.repository = repository or CommsLogRepository(incident_id, master_repo=master_repo)
        self.master_repo = master_repo or MasterRepository()
        self._last_resource_id: Optional[int] = None

    # ------------------------------------------------------------------
    # Entry CRUD
    # ------------------------------------------------------------------
    def create_entry(self, payload: Dict[str, Any]) -> CommsLogEntry:
        entry = self._entry_from_payload(payload)
        created = self.repository.add_entry(entry)
        if created.resource_id:
            try:
                self._last_resource_id = int(created.resource_id)
            except Exception:
                pass
        return created

    def quick_log(self, message: str, *, priority: Optional[str] = None, **extra: Any) -> CommsLogEntry:
        payload = dict(extra)
        payload.setdefault("message", message)
        if priority:
            payload.setdefault("priority", priority)
        if "resource_id" not in payload and self._last_resource_id is not None:
            payload["resource_id"] = self._last_resource_id
        created = self.create_entry(payload)
        return created

    def update_entry(self, entry_id: int, patch: Dict[str, Any]) -> CommsLogEntry:
        if not patch:
            return self.repository.get_entry(entry_id)
        if "attachments" in patch and isinstance(patch["attachments"], Iterable):
            patch["attachments"] = list(patch["attachments"])
        return self.repository.update_entry(entry_id, patch)

    def delete_entry(self, entry_id: int) -> None:
        self.repository.delete_entry(entry_id)

    def list_entries(self, query: Optional[CommsLogQuery] = None) -> List[CommsLogEntry]:
        return self.repository.list_entries(query)

    def get_entry(self, entry_id: int) -> CommsLogEntry:
        return self.repository.get_entry(entry_id)

    def list_audit(self, entry_id: int):
        return self.repository.list_audit_entries(entry_id)

    # ------------------------------------------------------------------
    # Filter presets
    # ------------------------------------------------------------------
    def list_filter_presets(self, user_id: Optional[str] = None) -> List[CommsLogFilterPreset]:
        return self.repository.list_filter_presets(user_id)

    def save_filter_preset(
        self,
        name: str,
        filters: Dict[str, Any],
        *,
        preset_id: Optional[int] = None,
        user_id: Optional[str] = None,
    ) -> CommsLogFilterPreset:
        return self.repository.save_filter_preset(name, filters, preset_id=preset_id, user_id=user_id)

    def delete_filter_preset(self, preset_id: int, *, user_id: Optional[str] = None) -> None:
        self.repository.delete_filter_preset(preset_id, user_id=user_id)

    # ------------------------------------------------------------------
    # Shortcut helpers
    # ------------------------------------------------------------------
    def list_channels(self) -> List[Dict[str, Any]]:
        try:
            return self.master_repo.list_channels()
        except Exception as exc:
            logger.warning("Unable to list channels: %s", exc)
            return []

    def last_used_resource(self) -> Optional[int]:
        return self._last_resource_id

    def mark_disposition(self, entry_id: int, disposition: str) -> CommsLogEntry:
        return self.repository.mark_disposition(entry_id, disposition)

    def mark_follow_up(self, entry_id: int, required: bool) -> CommsLogEntry:
        return self.repository.mark_follow_up(entry_id, required)

    def mark_status_update(self, entry_id: int, flag: bool) -> CommsLogEntry:
        return self.repository.mark_status_update(entry_id, flag)

    def attach_files(self, entry_id: int, paths: Iterable[str]) -> CommsLogEntry:
        entry = self.repository.get_entry(entry_id)
        existing = list(entry.attachments)
        for path in paths:
            if path and path not in existing:
                existing.append(path)
        return self.repository.update_entry(entry_id, {"attachments": existing})

    def list_contact_entities(self) -> List[Dict[str, Any]]:
        try:
            return self.repository.list_contact_entities()
        except Exception as exc:
            logger.warning("Unable to list communications contacts: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Integration helpers
    # ------------------------------------------------------------------
    def create_follow_up_task(self, entry_id: int, *, title: Optional[str] = None) -> Optional[int]:
        try:
            from modules.operations.taskings import repository as task_repo
        except Exception as exc:  # pragma: no cover - optional dependency
            logger.warning("Task module unavailable: %s", exc)
            return None

        entry = self.repository.get_entry(entry_id)
        base_title = title or entry.message.splitlines()[0][:60] or "Comms Follow-up"
        priority_map = {
            PRIORITY_ROUTINE: 2,
            PRIORITY_PRIORITY: 3,
            PRIORITY_EMERGENCY: 4,
        }
        priority = priority_map.get(entry.priority, 2)
        task_id = task_repo.create_task(title=base_title, priority=priority)
        self.repository.update_entry(entry_id, {"task_id": task_id, "follow_up_required": False})
        return task_id

    # ------------------------------------------------------------------
    # Export helpers
    # ------------------------------------------------------------------
    def export_to_csv(self, path: Path | str, query: Optional[CommsLogQuery] = None, *, metadata: Optional[Dict[str, Any]] = None) -> Path:
        entries = self.list_entries(query)
        target = Path(path)
        csv_exporter.export_entries(entries, target, metadata or self._default_export_metadata())
        return target

    def export_to_pdf(self, path: Path | str, query: Optional[CommsLogQuery] = None, *, metadata: Optional[Dict[str, Any]] = None) -> Path:
        entries = self.list_entries(query)
        target = Path(path)
        pdf_exporter.export_entries(entries, target, metadata or self._default_export_metadata())
        return target

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _entry_from_payload(self, payload: Dict[str, Any]) -> CommsLogEntry:
        data = dict(payload)
        attachments = data.get("attachments")
        if attachments is not None and not isinstance(attachments, list):
            data["attachments"] = list(attachments)
        entry = CommsLogEntry()
        for key, value in data.items():
            if hasattr(entry, key):
                setattr(entry, key, value)
        if not entry.operator_user_id:
            user = AppState.get_active_user_id()
            if user is not None:
                entry.operator_user_id = str(user)
        if entry.resource_id:
            try:
                self._last_resource_id = int(entry.resource_id)
            except Exception:
                pass
        return entry

    def _default_export_metadata(self) -> Dict[str, Any]:
        incident = AppState.get_active_incident()
        metadata = {
            "incident": incident or self.repository.incident_id,
            "generated_by": AppState.get_active_user_id(),
        }
        return metadata


__all__ = ["CommsLogService"]
