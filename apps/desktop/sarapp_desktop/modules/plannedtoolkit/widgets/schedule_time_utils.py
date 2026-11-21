"""Shared datetime helpers for the Event Schedule's views.

Both the Phase 1A/1B activity list and the Phase 1C operational timeline
need the same ISO-string <-> QDateTime conversions and planned-vs-actual
arithmetic — defined once here instead of duplicated per view.
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtWidgets import QDateTimeEdit


def parse_dt(value: str) -> datetime | None:
    if not value:
        return None
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        try:
            return datetime.fromisoformat(text.replace(" ", "T"))
        except ValueError:
            return None


def friendly_dt(value: str) -> str:
    dt = parse_dt(value)
    if dt is None:
        return ""
    return dt.strftime("%b %d  %H:%M")


def friendly_time(value: str) -> str:
    dt = parse_dt(value)
    if dt is None:
        return ""
    return dt.strftime("%H:%M")


def to_qdatetime(value: str) -> QDateTime:
    dt = parse_dt(value)
    if dt is None:
        return QDateTime.currentDateTime()
    return QDateTime(dt.year, dt.month, dt.day, dt.hour, dt.minute)


def storage_dt(editor: QDateTimeEdit) -> str:
    return editor.dateTime().toString(Qt.ISODate)


def minutes_diff(planned: str, actual: str) -> int | None:
    """Minutes `actual` is after `planned` (negative = early). None if either is unparsable."""
    planned_dt = parse_dt(planned)
    actual_dt = parse_dt(actual)
    if planned_dt is None or actual_dt is None:
        return None
    return round((actual_dt - planned_dt).total_seconds() / 60)


def planned_vs_actual_text(starts_at: str, ends_at: str, actual_start_at: str, actual_end_at: str) -> str:
    """A concise, computed (never stored) planned-vs-actual summary.

    Prefers the end-time comparison once an activity has an actual end
    (the more complete picture); falls back to the start-time comparison
    while it's still only actually started.
    """
    if actual_end_at:
        diff = minutes_diff(ends_at, actual_end_at)
        if diff is not None:
            if diff > 0:
                return f"Finished {diff} min late"
            if diff < 0:
                return f"Finished {abs(diff)} min early"
            return "Finished on schedule"
    if actual_start_at:
        diff = minutes_diff(starts_at, actual_start_at)
        if diff is not None:
            if diff > 0:
                return f"Started {diff} min late"
            if diff < 0:
                return f"Started {abs(diff)} min early"
            return "Started on schedule"
    return ""


_OPEN_STATUSES = ("Scheduled", "In Progress", "Delayed")


def is_overdue(status: str, starts_at: str, ends_at: str, *, now: datetime | None = None) -> bool:
    """True when an activity's planned time has passed but it's still open.

    Deliberately a *computed* read of "needs attention" — per the brief,
    an activity may be overdue without the schedule ever marking it
    Delayed (that status change is still a human action).
    """
    if status not in _OPEN_STATUSES:
        return False
    reference = parse_dt(ends_at) or parse_dt(starts_at)
    if reference is None:
        return False
    now = now or datetime.now(reference.tzinfo)
    return reference < now
