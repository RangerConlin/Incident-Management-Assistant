"""WorkAssignmentDesk — live, cache-backed Work Assignment list + board metadata.

Reads the `work_assignments` collection out of `incident_cache` (populated on
incident load and kept current over the WebSocket, see
`utils/incident_cache_loader.py`) instead of the planner board issuing its own
list + per-assignment resource/hazard/task-link requests. Each Work Assignment
document already embeds its resources, hazards, and task links, so one cache
read is enough to compute the board's badge metadata for every card — no
network round trip at all, and it updates live when any client writes a
change, including this one.

Mirrors `modules/statusboards/team_task_desk.py`'s pattern: a small QObject
that stitches raw cache documents into the shape a board needs and emits a
signal whenever the underlying collection changes.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from PySide6.QtCore import QObject, Signal

from modules.planning.tactics_resources.data.work_assignment_repository import wa_from_dict
from modules.planning.tactics_resources.models.work_assignment_models import WorkAssignment
from utils.incident_cache import incident_cache

logger = logging.getLogger(__name__)

_COLLECTION = "work_assignments"

# (total_required, total_assigned, total_gap, hazard_count, open_hazard_count, task_link_count)
WorkAssignmentMeta = tuple[int, int, int, int, int, int]
EMPTY_META: WorkAssignmentMeta = (0, 0, 0, 0, 0, 0)


def _meta_from_doc(doc: dict[str, Any]) -> WorkAssignmentMeta:
    resources = doc.get("resources") or []
    hazards = doc.get("hazards") or []
    task_links = doc.get("task_links") or []
    req_total = sum(int(r.get("quantity_required") or 0) for r in resources)
    assigned_total = sum(int(r.get("quantity_assigned") or 0) for r in resources)
    gap = sum(max(int(r.get("quantity_required") or 0) - int(r.get("quantity_assigned") or 0), 0) for r in resources)
    open_hazards = sum(1 for h in hazards if not h.get("is_resolved"))
    return (req_total, assigned_total, gap, len(hazards), open_hazards, len(task_links))


def _wa_from_cache_doc(doc: dict[str, Any]) -> WorkAssignment:
    return wa_from_dict({**doc, "id": doc.get("int_id")})


def resolve_person_name(person_id: Any) -> str:
    """Resolve a personnel record id to a display name via `incident_cache`
    (no network call) — the same cache-only pattern as
    `modules/statusboards/team_task_desk.py`'s `_resolve_leader`. Falls back
    to the id itself, stringified, if it can't be resolved."""
    if not person_id:
        return ""
    try:
        target = int(person_id)
    except (TypeError, ValueError):
        return str(person_id)
    try:
        personnel = incident_cache.get_all("incident_personnel")
    except Exception:
        return str(person_id)
    for person in personnel:
        pid = person.get("person_record") or person.get("master_id")
        try:
            if pid is None or int(pid) != target:
                continue
        except (TypeError, ValueError):
            continue
        name = person.get("name") or f"{person.get('first_name') or ''} {person.get('last_name') or ''}".strip()
        return name or str(person_id)
    return str(person_id)


def _matches_filters(doc: dict[str, Any], filters: dict[str, Any]) -> bool:
    if doc.get("deleted"):
        return False
    if not filters.get("show_archived") and doc.get("is_archived"):
        return False
    for field in ("planning_status", "safety_status", "resource_status", "branch", "division_group"):
        if filters.get(field) and doc.get(field) != filters[field]:
            return False
    if filters.get("op_period_id") is not None and doc.get("operational_period_id") != filters["op_period_id"]:
        return False
    if filters.get("objective_id") is not None and doc.get("objective_id") != filters["objective_id"]:
        return False
    search = str(filters.get("search") or "").strip().lower()
    if search:
        haystack = (str(doc.get("assignment_name") or ""), str(doc.get("assignment_number") or ""))
        if not any(search in value.lower() for value in haystack):
            return False
    return True


class WorkAssignmentDesk(QObject):
    """Live Work Assignment list for the Tactics and Resources board.

    `changed` fires with no arguments whenever anything in the
    `work_assignments` collection changes (any client, including this one) —
    callers are expected to just re-query `list_with_meta` and re-render.
    """

    changed = Signal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        incident_cache.changed.connect(self._on_cache_changed)
        incident_cache.snapshotLoaded.connect(self._on_snapshot_loaded)

    def _on_cache_changed(self, collection: str, op: str, doc_id: str) -> None:
        if collection == _COLLECTION:
            self.changed.emit()

    def _on_snapshot_loaded(self) -> None:
        self.changed.emit()

    def meta_for(self, work_assignment_id: int) -> WorkAssignmentMeta:
        """Return the computed metadata for one Work Assignment, by its
        public `int_id`. Zero network calls — reads the already-cached doc."""
        try:
            docs = incident_cache.get_all(_COLLECTION)
        except Exception:
            logger.exception("WorkAssignmentDesk failed to read incident_cache")
            return EMPTY_META
        doc = next((d for d in docs if d.get("int_id") == work_assignment_id), None)
        return _meta_from_doc(doc) if doc is not None else EMPTY_META

    def list_with_meta(
        self, filters: dict[str, Any] | None = None
    ) -> list[tuple[WorkAssignment, WorkAssignmentMeta]]:
        """Return every Work Assignment matching `filters`, each paired with
        its computed board metadata. Mirrors the filter semantics the
        `/planning/work-assignments` list endpoint used to apply server-side."""
        filters = filters or {}
        try:
            docs = incident_cache.get_all(_COLLECTION)
        except Exception:
            logger.exception("WorkAssignmentDesk failed to read incident_cache")
            return []

        results = [
            (_wa_from_cache_doc(doc), _meta_from_doc(doc))
            for doc in docs
            if _matches_filters(doc, filters)
        ]
        results.sort(key=lambda pair: pair[0].updated_at or "", reverse=True)
        return results


# Module-level singleton — import and use directly.
work_assignment_desk = WorkAssignmentDesk()

__all__ = [
    "work_assignment_desk",
    "WorkAssignmentDesk",
    "WorkAssignmentMeta",
    "EMPTY_META",
    "resolve_person_name",
]
