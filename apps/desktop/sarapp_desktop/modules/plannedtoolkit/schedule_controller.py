"""Shared, live-updating data source for the Event Schedule's views.

Phase 1A/1B's activity list and Phase 1C's operational timeline both read
from this one controller instead of each fetching/filtering independently —
one source of truth, one refresh path, one live-update subscription, per
"do not create a second scheduling system." Every mutation here calls the
same `services.py` wrappers (and therefore the same validated backend
endpoints) Phase 1A/1B already built; this file adds no new status-changing
logic of its own.

Live updates: `BaseRepository` broadcasts every write on
`planned_event_schedules` over the incident WebSocket regardless of which
client made it; the desktop WS client already routes that into
`utils.incident_cache.incident_cache`, whose `changed` signal this
controller subscribes to. That is the application's existing
synchronization mechanism — this file adds no new WebSocket or polling of
its own.
"""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, Signal

from . import services
from .records import ScheduledItem
from utils.api_client import APIError
from utils.incident_cache import incident_cache

# Must match sarapp_db.mongo.collection_names.IncidentCollections.PLANNED_EVENT_SCHEDULES.
SCHEDULE_COLLECTION = "planned_event_schedules"


class ScheduleController(QObject):
    """Owns the current incident's schedule items and all mutations on them."""

    itemsChanged = Signal()
    statusMessage = Signal(str, bool)  # (message, is_error)

    def __init__(self, incident_id: str | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.incident_id = None if incident_id is None else str(incident_id)
        self._items: list[ScheduledItem] = []
        incident_cache.changed.connect(self._on_cache_changed)
        self.refresh()

    def _on_cache_changed(self, collection: str, _op: str, _doc_id: str) -> None:
        if collection == SCHEDULE_COLLECTION:
            self.refresh()

    def items(self) -> list[ScheduledItem]:
        return list(self._items)

    def _describe_error(self, exc: Exception) -> str:
        if isinstance(exc, APIError):
            if exc.status_code is None:
                return f"Schedule API unavailable: {exc}"
            return f"Schedule API error {exc.status_code}: {exc}"
        return str(exc)

    def refresh(self) -> None:
        if not self.incident_id:
            self._items = []
            self.itemsChanged.emit()
            self.statusMessage.emit("Select an incident to use the Event Schedule.", True)
            return
        try:
            rows = services.list_schedule_items(self.incident_id)
        except Exception as exc:
            self._items = []
            self.itemsChanged.emit()
            self.statusMessage.emit(self._describe_error(exc), True)
            return
        self._items = sorted(rows, key=lambda row: row.starts_at or "")
        self.itemsChanged.emit()
        self.statusMessage.emit(f"{len(self._items)} activities", False)

    def _run(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> bool:
        try:
            fn(*args, **kwargs)
        except Exception as exc:
            self.statusMessage.emit(self._describe_error(exc), True)
            return False
        self.refresh()
        return True

    def create(self, **payload: Any) -> bool:
        return self._run(services.create_schedule_item, self.incident_id, **payload)

    def update(self, record_id: int, patch: dict[str, Any]) -> bool:
        return self._run(services.update_schedule_item, record_id, patch, self.incident_id)

    def delete(self, record_id: int) -> bool:
        return self._run(services.delete_schedule_item, record_id, self.incident_id)

    def start(self, record_id: int) -> bool:
        return self._run(services.start_schedule_item, record_id, self.incident_id)

    def resume(self, record_id: int) -> bool:
        return self._run(services.resume_schedule_item, record_id, self.incident_id)

    def complete(self, record_id: int) -> bool:
        return self._run(services.complete_schedule_item, record_id, self.incident_id)

    def delay(self, record_id: int, *, delay_reason: str) -> bool:
        return self._run(services.delay_schedule_item, record_id, self.incident_id, delay_reason=delay_reason)

    def cancel(self, record_id: int, *, cancellation_reason: str) -> bool:
        return self._run(
            services.cancel_schedule_item, record_id, self.incident_id, cancellation_reason=cancellation_reason
        )

    def create_quick_assignment(self, record_id: int) -> bool:
        return self._run(services.create_quick_assignment_from_schedule_item, record_id, self.incident_id)
