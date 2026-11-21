"""Shared, live-updating data source for the Event Schedule's views.

Phase 1A/1B's activity list and Phase 1C's operational timeline both read
from this one controller instead of each fetching/filtering independently —
one source of truth, one refresh path, one live-update subscription, per
"do not create a second scheduling system." Every mutation here calls the
same `services.py` wrappers (and therefore the same validated backend
endpoints) Phase 1A/1B built; this file adds no new status-changing logic
of its own.

Live updates: `BaseRepository` broadcasts every write on
`planned_event_schedules` over the incident WebSocket regardless of which
client made it; the desktop WS client already routes that into
`utils.incident_cache.incident_cache`, whose `changed` signal this
controller subscribes to. That is the application's existing
synchronization mechanism — this file adds no new WebSocket or polling of
its own.

Phase 1E: `refresh()` on a transient connection failure keeps the last
known-good `_items` instead of wiping the display to empty (a temporary
disconnect must not destroy what's on screen). Every mutation accepts an
`expected_revision` -- the item's own `revision` field, which the backend
increments by exactly 1 on every write and compares against, per
`plannedtoolkit.py`'s `_check_schedule_concurrency` -- so two operators
editing the same activity can't silently overwrite each other; a 409
conflict triggers an immediate `refresh()` so the caller's next read is the
server's real current state (the brief's "allow the user to reload").
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
    conflict = Signal(str)  # emitted (with the error message) on a 409

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

    def item_by_id(self, record_id: int) -> ScheduledItem | None:
        return next((item for item in self._items if item.id == record_id), None)

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
            # A temporary disconnect must not wipe what's already on
            # screen -- keep the last known-good items and just report the
            # error; the next live-update or manual refresh recovers.
            self.statusMessage.emit(self._describe_error(exc), True)
            return
        self._items = sorted(rows, key=lambda row: row.starts_at or "")
        self.itemsChanged.emit()
        self.statusMessage.emit(f"{len(self._items)} activities", False)

    def _run(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> bool:
        try:
            fn(*args, **kwargs)
        except Exception as exc:
            message = self._describe_error(exc)
            is_conflict = isinstance(exc, APIError) and exc.status_code == 409
            self.statusMessage.emit(message, True)
            if is_conflict:
                self.conflict.emit(message)
                # Resync to the server's real state so the next retry (or
                # just looking at the screen) reflects what actually won.
                self.refresh()
            return False
        self.refresh()
        return True

    def create(self, **payload: Any) -> bool:
        return self._run(services.create_schedule_item, self.incident_id, **payload)

    def update(self, record_id: int, patch: dict[str, Any], *, expected_revision: int | None = None) -> bool:
        if expected_revision is not None:
            patch = {**patch, "expected_revision": expected_revision}
        return self._run(services.update_schedule_item, record_id, patch, self.incident_id)

    def delete(self, record_id: int) -> bool:
        return self._run(services.delete_schedule_item, record_id, self.incident_id)

    def start(self, record_id: int, *, expected_revision: int | None = None) -> bool:
        return self._run(services.start_schedule_item, record_id, self.incident_id, expected_revision=expected_revision)

    def resume(self, record_id: int, *, expected_revision: int | None = None) -> bool:
        return self._run(services.resume_schedule_item, record_id, self.incident_id, expected_revision=expected_revision)

    def complete(self, record_id: int, *, expected_revision: int | None = None) -> bool:
        return self._run(services.complete_schedule_item, record_id, self.incident_id, expected_revision=expected_revision)

    def delay(
        self,
        record_id: int,
        *,
        delay_reason: str,
        revised_start_at: str | None = None,
        expected_revision: int | None = None,
    ) -> bool:
        return self._run(
            services.delay_schedule_item, record_id, self.incident_id,
            delay_reason=delay_reason, revised_start_at=revised_start_at, expected_revision=expected_revision,
        )

    def cancel(self, record_id: int, *, cancellation_reason: str, expected_revision: int | None = None) -> bool:
        return self._run(
            services.cancel_schedule_item, record_id, self.incident_id,
            cancellation_reason=cancellation_reason, expected_revision=expected_revision,
        )

    def correct(
        self,
        record_id: int,
        *,
        reason: str,
        status: str | None = None,
        actual_start_at: str | None = None,
        actual_end_at: str | None = None,
        expected_revision: int | None = None,
    ) -> bool:
        return self._run(
            services.correct_schedule_item, record_id, self.incident_id,
            reason=reason, status=status, actual_start_at=actual_start_at,
            actual_end_at=actual_end_at, expected_revision=expected_revision,
        )

    def create_quick_assignment(self, record_id: int) -> bool:
        return self._run(services.create_quick_assignment_from_schedule_item, record_id, self.incident_id)
