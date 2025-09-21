"""Utility helpers for rendering timestamps in the UI."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional


_LOCAL_TZ = datetime.now().astimezone().tzinfo or timezone.utc


def _coerce_datetime(value: Any) -> Optional[datetime]:
    """Best-effort conversion to an aware ``datetime`` in the local timezone."""

    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(value, tz=timezone.utc)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        # Support common ISO formats with and without timezone
        for candidate in (_try_isoformat, _try_datetime_from_formats):
            dt = candidate(text)
            if dt is not None:
                break
        else:
            return None
    else:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_LOCAL_TZ)
    return dt.astimezone(_LOCAL_TZ)


def _try_isoformat(value: str) -> Optional[datetime]:
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        return None


_KNOWN_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S.%f",
)


def _try_datetime_from_formats(value: str) -> Optional[datetime]:
    for fmt in _KNOWN_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def humanize_relative(value: Any, *, now: Any | None = None, default: str = "—") -> str:
    """Return a compact ``hh:mm`` style label describing how long ago ``value`` occurred."""

    dt = _coerce_datetime(value)
    if dt is None:
        return default

    reference = _coerce_datetime(now) if now is not None else datetime.now(tz=_LOCAL_TZ)
    if reference is None:
        reference = datetime.now(tz=_LOCAL_TZ)

    delta = reference - dt
    sign = 1
    if delta.total_seconds() < 0:
        delta = -delta
        sign = -1

    minutes = int(delta.total_seconds() // 60)
    seconds = int(delta.total_seconds() % 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if days == 0 and (hours or minutes):
        parts.append(f"{minutes:02d}m" if hours else f"{minutes}m")
    if not parts:
        parts.append(f"{seconds}s")

    label = " ".join(parts)
    if sign < 0:
        return f"in {label}"
    if label in {"0s", "0m"}:
        return "just now"
    return f"{label} ago"


def format_local_hhmm(value: Any, default: str = "—") -> str:
    """Format ``value`` as a localised HH:MM time string."""

    dt = _coerce_datetime(value)
    if dt is None:
        return default
    return dt.strftime("%H:%M")


def minutes_since(value: Any, *, now: Any | None = None) -> Optional[int]:
    """Return the number of minutes elapsed since ``value`` (positive for past events)."""

    dt = _coerce_datetime(value)
    if dt is None:
        return None
    reference = _coerce_datetime(now) if now is not None else datetime.now(tz=_LOCAL_TZ)
    if reference is None:
        reference = datetime.now(tz=_LOCAL_TZ)
    diff = reference - dt
    return int(diff.total_seconds() // 60)


def to_datetime(value: Any) -> Optional[datetime]:
    """Public wrapper exposing the internal conversion helper."""

    return _coerce_datetime(value)


__all__ = [
    "humanize_relative",
    "format_local_hhmm",
    "minutes_since",
    "to_datetime",
]
