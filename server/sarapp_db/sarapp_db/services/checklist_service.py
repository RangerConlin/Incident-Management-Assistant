"""Shared Checklist domain logic: program-wide, not owned by any one module.

This module is pure/stateless (no Mongo access of its own, like
`api/routers/gar_templates.py::score_selections`) so it is independently
unit-testable and so any feature module — Planned Events today, others
later — can reuse the same rules without importing a router. The two
routers that do touch Mongo (`api/routers/checklist_templates.py` for the
catalog, `api/routers/checklists.py` for per-incident instances) both call
into this module rather than re-implementing any of it.

Item shape (shared by a template item and a snapshotted instance item)::

    {
        "id": str,
        "item_type": one of ITEM_TYPES,
        "label": str,
        "instructions": str,
        "required": bool,
        "na_allowed": bool,
        "options": [{"id": str, "label": str}, ...],   # selection only
        "unit": str,                                    # numeric only
        "min_value": float | None,                       # numeric only
        "max_value": float | None,                       # numeric only
    }

An instance item additionally carries::

    {
        "response": {
            "value": Any,
            "na": bool,
            "notes": str,
            "recorded_by": int,
            "recorded_at": str (ISO8601 UTC),
        } | None,
        "history": [<response entry>, ...],   # append-only, oldest first
    }

``response`` always mirrors ``history[-1]`` — it is never edited in place,
so a response entry's own ``recorded_by``/``recorded_at`` doubles as both
"who/when this response was recorded" and "who/when it was last modified"
(the latest entry *is* the latest modification). An earlier entry an item
had before someone else recorded a new response is left untouched in
``history``, so its original author and timestamp are never lost.

A section is ``{"id": str, "name": str, "items": [<item>, ...]}``. A
section's ``name`` may be blank — sections are optional per the product
spec, and an unnamed section is how a template represents "no sections",
without needing a second, parallel items-outside-sections structure.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

CHECKBOX = "checkbox"
PASS_FAIL_NA = "pass_fail_na"
TEXT = "text"
NUMERIC = "numeric"
SELECTION = "selection"

ITEM_TYPES = {CHECKBOX, PASS_FAIL_NA, TEXT, NUMERIC, SELECTION}

NOT_STARTED = "not_started"
IN_PROGRESS = "in_progress"
COMPLETED = "completed"
ARCHIVED = "archived"

CHECKLIST_STATUSES = {NOT_STARTED, IN_PROGRESS, COMPLETED, ARCHIVED}

# Full finalization semantics (e.g. ICS-214 logging on completion) are
# Phase 4B. Phase 4A only needs the state machine's boundaries: completion,
# reopening, and archiving. ARCHIVED is terminal for 4A — unarchiving is
# explicitly deferred.
STATUS_TRANSITIONS: Dict[str, set] = {
    NOT_STARTED: {IN_PROGRESS, ARCHIVED},
    IN_PROGRESS: {COMPLETED, ARCHIVED},
    COMPLETED: {IN_PROGRESS, ARCHIVED},
    ARCHIVED: set(),
}


class ChecklistValidationError(ValueError):
    """Raised for any shape/response validation failure; callers translate to HTTP 422."""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Template/section/item shape validation
# ---------------------------------------------------------------------------

def validate_item_shape(item: Dict[str, Any]) -> None:
    """Validate one template item definition. Raises ChecklistValidationError."""

    item_type = item.get("item_type")
    if item_type not in ITEM_TYPES:
        raise ChecklistValidationError(f"Unknown item_type: {item_type!r}")

    if not str(item.get("label") or "").strip():
        raise ChecklistValidationError(f"Item {item.get('id')!r} requires a label")

    if item_type == SELECTION:
        options = item.get("options") or []
        if not options:
            raise ChecklistValidationError(
                f"Selection item {item.get('id')!r} requires at least one option"
            )
        option_ids = {opt["id"] for opt in options}
        if len(option_ids) != len(options):
            raise ChecklistValidationError(
                f"Selection item {item.get('id')!r} has duplicate option ids"
            )

    if item_type == NUMERIC:
        min_value = item.get("min_value")
        max_value = item.get("max_value")
        if min_value is not None and max_value is not None and float(min_value) > float(max_value):
            raise ChecklistValidationError(
                f"Numeric item {item.get('id')!r} has min_value greater than max_value"
            )


def validate_template_shape(sections: List[Dict[str, Any]]) -> None:
    """Validate a whole ordered sections/items tree.

    Item ids must be unique across the *entire* template, not just within
    one section — an instance response is recorded by item id alone, so a
    duplicate anywhere would make responses ambiguous.
    """

    section_ids: set = set()
    item_ids: set = set()
    for section in sections:
        section_id = section.get("id")
        if section_id in section_ids:
            raise ChecklistValidationError(f"Duplicate section id: {section_id}")
        section_ids.add(section_id)
        for item in section.get("items") or []:
            item_id = item.get("id")
            if item_id in item_ids:
                raise ChecklistValidationError(f"Duplicate item id: {item_id}")
            item_ids.add(item_id)
            validate_item_shape(item)


# ---------------------------------------------------------------------------
# Template -> instance snapshotting
# ---------------------------------------------------------------------------

def snapshot_sections(template_sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deep-copy a template's sections/items into a fresh instance tree.

    The result has no live reference back to the template — editing or
    deleting the source template afterward never changes an instance that
    already snapshotted it.
    """

    snapshot = copy.deepcopy(template_sections)
    for section in snapshot:
        for item in section.get("items") or []:
            item["response"] = None
            item["history"] = []
    return snapshot


def iter_items(sections: List[Dict[str, Any]]):
    """Yield (section, item) for every item across every section, in order."""

    for section in sections or []:
        for item in section.get("items") or []:
            yield section, item


def find_item(sections: List[Dict[str, Any]], item_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    for section, item in iter_items(sections):
        if item.get("id") == item_id:
            return section, item
    return None, None


# ---------------------------------------------------------------------------
# Response validation
# ---------------------------------------------------------------------------

def validate_and_normalize_response(
    item: Dict[str, Any], value: Any, na: bool
) -> Tuple[Any, bool]:
    """Validate a submitted response against its item definition.

    Returns the normalized ``(value, na)`` pair to persist. Raises
    ChecklistValidationError (-> HTTP 422) on an invalid submission.

    N/A is represented the same way for every item type: ``na=True`` and
    ``value=None``, regardless of ``item_type``. A failed Pass/Fail/N/A
    result is stored as ``value="fail", na=False`` so it stays
    distinguishable from both "unanswered" (no response at all) and
    "marked N/A" (na=True).
    """

    if na:
        if not item.get("na_allowed"):
            raise ChecklistValidationError(
                f"Item {item.get('id')!r} does not allow an N/A response"
            )
        return None, True

    item_type = item["item_type"]
    required = bool(item.get("required"))

    if item_type == CHECKBOX:
        if not isinstance(value, bool):
            raise ChecklistValidationError("Checkbox response must be true or false")
        return value, False

    if item_type == PASS_FAIL_NA:
        if value not in ("pass", "fail"):
            raise ChecklistValidationError(
                "Pass/Fail/N/A response must be 'pass' or 'fail' (use na=true for N/A)"
            )
        return value, False

    if item_type == TEXT:
        text = str(value or "").strip()
        if required and not text:
            raise ChecklistValidationError(f"Item {item.get('id')!r} requires a response")
        return text, False

    if item_type == NUMERIC:
        if value is None or isinstance(value, bool):
            raise ChecklistValidationError("Numeric response requires a number")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ChecklistValidationError("Numeric response must be a number") from exc
        min_value = item.get("min_value")
        max_value = item.get("max_value")
        if min_value is not None and number < float(min_value):
            raise ChecklistValidationError(
                f"Value {number} is below the minimum of {min_value}"
            )
        if max_value is not None and number > float(max_value):
            raise ChecklistValidationError(
                f"Value {number} is above the maximum of {max_value}"
            )
        return number, False

    if item_type == SELECTION:
        option_ids = {opt["id"] for opt in item.get("options") or []}
        if value not in option_ids:
            raise ChecklistValidationError(
                f"'{value}' is not one of this item's configured options"
            )
        return value, False

    raise ChecklistValidationError(f"Unknown item_type: {item_type!r}")


def build_response_entry(
    value: Any, na: bool, notes: str, actor_id: int, now: Optional[str] = None
) -> Dict[str, Any]:
    """A fresh, server-attributed response-history entry.

    Timestamps and author identity are always server-generated from the
    authenticated caller (``actor_id``) — never taken from client input.
    """

    stamp = now or _utcnow_iso()
    return {
        "value": value,
        "na": na,
        "notes": str(notes or ""),
        "recorded_by": actor_id,
        "recorded_at": stamp,
    }


def record_response(
    item: Dict[str, Any], value: Any, na: bool, notes: str, actor_id: int
) -> Dict[str, Any]:
    """Validate, then append a new response-history entry onto ``item`` in place.

    Returns the new current response entry. The previous current response
    (if any) is left untouched in ``history`` — nothing is ever overwritten,
    so the original author/timestamp of an earlier response survives even
    when a different user changes it later. ``item["response"]`` always
    mirrors ``item["history"][-1]`` after this call.

    This in-place/read-modify-write form is for pure in-memory use (unit
    tests, previews). `api/routers/checklists.py`'s actual persistence path
    uses a targeted, atomic `$push`/`$set` with Mongo array filters instead,
    so two concurrent responses to two *different* items on the same
    checklist can never clobber each other.
    """

    normalized_value, normalized_na = validate_and_normalize_response(item, value, na)
    entry = build_response_entry(normalized_value, normalized_na, notes, actor_id)
    item.setdefault("history", []).append(entry)
    item["response"] = entry
    return entry


def is_answered(item: Dict[str, Any]) -> bool:
    """An item is answered as soon as it carries any valid response.

    A failed Pass/Fail/N/A result counts as answered — it is an unresolved
    *failure*, not an unanswered item. There is no separate
    "mark complete" action for an item; recording a valid response is
    the completion action.
    """

    return item.get("response") is not None


def is_failed(item: Dict[str, Any]) -> bool:
    """True for a current (not historical) Pass/Fail/N/A response of 'fail'."""

    response = item.get("response")
    return bool(
        response
        and not response.get("na")
        and item.get("item_type") == PASS_FAIL_NA
        and response.get("value") == "fail"
    )


# ---------------------------------------------------------------------------
# Progress / failure calculation
# ---------------------------------------------------------------------------

def compute_progress(sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Backend-calculated summary for a checklist instance.

    Definitions (documented once here; every caller must use this function
    rather than recomputing the rule elsewhere):
      - ``total_items``: every item across every section.
      - ``answered_items``: items with any current response, N/A included.
      - ``unanswered_required_items``: required items with no response yet.
      - ``na_items``: items whose current response is marked N/A.
      - ``failed_items``: items whose current Pass/Fail/N/A response is
        'fail' — an answered item is *not* assumed satisfactory just
        because it is answered, and this checklist is never
        auto-completed just because every item got a response.
      - ``completion_percentage``: answered_items / total_items * 100,
        rounded to one decimal place (0.0 when there are no items).
    """

    total_items = 0
    answered_items = 0
    unanswered_required_items: List[str] = []
    na_items = 0
    failed_items: List[str] = []

    for _section, item in iter_items(sections):
        total_items += 1
        answered = is_answered(item)
        if answered:
            answered_items += 1
            response = item.get("response") or {}
            if response.get("na"):
                na_items += 1
        elif item.get("required"):
            unanswered_required_items.append(item["id"])
        if is_failed(item):
            failed_items.append(item["id"])

    completion_percentage = (
        round((answered_items / total_items) * 100, 1) if total_items else 0.0
    )

    return {
        "total_items": total_items,
        "answered_items": answered_items,
        "unanswered_required_items": unanswered_required_items,
        "na_items": na_items,
        "failed_items": failed_items,
        "completion_percentage": completion_percentage,
    }


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def apply_status_transition(current_status: str, new_status: str) -> None:
    """Validate a status transition. Raises ChecklistValidationError if disallowed."""

    if new_status not in CHECKLIST_STATUSES:
        raise ChecklistValidationError(f"Unknown status: {new_status!r}")
    if new_status == current_status:
        return
    allowed = STATUS_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        raise ChecklistValidationError(
            f"Cannot move checklist from '{current_status}' to '{new_status}'"
        )


def status_after_first_response(current_status: str) -> str:
    """NOT_STARTED -> IN_PROGRESS happens automatically on the first response."""

    return IN_PROGRESS if current_status == NOT_STARTED else current_status
