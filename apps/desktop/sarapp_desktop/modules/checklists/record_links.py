"""Registry mapping a `linked_records` entry's `record_type` to how to
show/open that record, without `modules.checklists` depending on
Planned Events (or any other module).

A module that wants its own record type to be navigable from a
checklist's "Associated Records" list registers a handler here, at its
own import time, instead of this module reaching out and importing that
module directly — the same "extension point, not a hard dependency"
shape `checklist_service`'s ICS-214 stream priority-2 resolver documents
server-side. `modules.plannedtoolkit` is the first (and, as of Phase 4D,
only) registrant — see `modules/plannedtoolkit/checklist_links.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

ResolveLabel = Callable[[str, str], str]  # (incident_id, record_id) -> display label
OpenRecord = Callable[[str, str, object], None]  # (incident_id, record_id, parent_widget)


@dataclass(frozen=True)
class RecordLinkHandler:
    type_label: str  # human name for the record_type, e.g. "Schedule Activity"
    resolve_label: ResolveLabel
    open_record: Optional[OpenRecord] = None


_REGISTRY: dict[str, RecordLinkHandler] = {}


def register(record_type: str, handler: RecordLinkHandler) -> None:
    _REGISTRY[record_type] = handler


def get_handler(record_type: str) -> Optional[RecordLinkHandler]:
    return _REGISTRY.get(record_type)


def describe(incident_id: str, record_type: str, record_id: str) -> str:
    """Best-effort human label for one `linked_records` entry.

    Falls back to a plain "type: id" string when no handler is
    registered for `record_type`, or when resolving the label fails
    (e.g. the record was since deleted) — callers should never let a
    label-resolution failure break rendering the rest of the list."""

    handler = get_handler(record_type)
    if handler is None:
        return f"{record_type}: {record_id}"
    try:
        return f"{handler.type_label}: {handler.resolve_label(incident_id, record_id)}"
    except Exception:
        return f"{handler.type_label}: {record_id} (unavailable)"


def can_open(record_type: str) -> bool:
    handler = get_handler(record_type)
    return bool(handler and handler.open_record)


def open_record(incident_id: str, record_type: str, record_id: str, parent: object) -> None:
    handler = get_handler(record_type)
    if handler is None or handler.open_record is None:
        return
    handler.open_record(incident_id, record_id, parent)


__all__ = ["RecordLinkHandler", "register", "get_handler", "describe", "can_open", "open_record"]
