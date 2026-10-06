"""Utility helpers for rendering timestamps in the UI."""
from __future__ import annotations

from datetime import datetime, timezone, tzinfo
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil import tz as dateutil_tz


_LOCAL_TZ = datetime.now().astimezone().tzinfo or timezone.utc
DISPLAY_TIMEZONE_SETTING = "displayTimeZone"
SYSTEM_TIMEZONE_KEY = "system"

_COMMON_TIMEZONES: tuple[tuple[str, str], ...] = (
    (SYSTEM_TIMEZONE_KEY, "System time zone"),
    ("UTC", "UTC"),
    ("America/New_York", "Eastern Time"),
    ("America/Chicago", "Central Time"),
    ("America/Denver", "Mountain Time"),
    ("America/Phoenix", "Arizona Time"),
    ("America/Los_Angeles", "Pacific Time"),
    ("America/Anchorage", "Alaska Time"),
    ("Pacific/Honolulu", "Hawaii Time"),
)


def _coerce_datetime(
    value: Any,
    *,
    target_tz: tzinfo | None = None,
    assume_naive_utc: bool = False,
) -> Optional[datetime]:
    """Best-effort conversion to an aware ``datetime`` in the requested timezone."""

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
        dt = dt.replace(tzinfo=timezone.utc if assume_naive_utc else _LOCAL_TZ)
    return dt.astimezone(target_tz or get_display_timezone())


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


def display_timezone_options() -> tuple[tuple[str, str], ...]:
    """Return the supported display timezone choices as ``(key, label)`` pairs."""

    return _COMMON_TIMEZONES


def get_display_timezone_key(default: str = SYSTEM_TIMEZONE_KEY) -> str:
    """Read the persisted display timezone key from app settings."""

    try:
        from utils.settingsmanager import SettingsManager

        value = SettingsManager().get(DISPLAY_TIMEZONE_SETTING, default)
    except Exception:
        value = default
    key = str(value or default).strip()
    valid = {option_key for option_key, _label in _COMMON_TIMEZONES}
    return key if key in valid else default


def get_display_timezone() -> tzinfo:
    """Return the configured display timezone, falling back to the system timezone."""

    key = get_display_timezone_key()
    if key == SYSTEM_TIMEZONE_KEY:
        return _LOCAL_TZ
    if key == "UTC":
        return timezone.utc
    try:
        return ZoneInfo(key)
    except ZoneInfoNotFoundError:
        fallback = dateutil_tz.gettz(key)
        return fallback or _LOCAL_TZ


def format_display_datetime(
    value: Any,
    *,
    default: str = "",
    include_seconds: bool = True,
    include_timezone: bool = False,
) -> str:
    """Format a stored timestamp in the user-selected display timezone."""

    dt = _coerce_datetime(value, assume_naive_utc=True)
    if dt is None:
        return default
    fmt = "%m/%d/%Y %H:%M:%S" if include_seconds else "%m/%d/%Y %H:%M"
    text = dt.strftime(fmt)
    if include_timezone:
        tz_name = abbreviate_tz_name(dt.tzname() or "")
        if tz_name:
            text = f"{text} {tz_name}"
    return text


def humanize_relative(value: Any, *, now: Any | None = None, default: str = "—") -> str:
    """Return a compact ``hh:mm`` style label describing how long ago ``value`` occurred."""

    dt = _coerce_datetime(value)
    if dt is None:
        return default

    reference = _coerce_datetime(now) if now is not None else datetime.now(tz=get_display_timezone())
    if reference is None:
        reference = datetime.now(tz=get_display_timezone())

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
    reference = _coerce_datetime(now) if now is not None else datetime.now(tz=get_display_timezone())
    if reference is None:
        reference = datetime.now(tz=get_display_timezone())
    diff = reference - dt
    return int(diff.total_seconds() // 60)


def to_datetime(value: Any) -> Optional[datetime]:
    """Public wrapper exposing the internal conversion helper."""

    return _coerce_datetime(value)


_TZ_ABBR_MAP = {
    'Eastern Standard Time': 'EST',
    'Eastern Daylight Time': 'EDT',
    'Central Standard Time': 'CST',
    'Central Daylight Time': 'CDT',
    'Mountain Standard Time': 'MST',
    'Mountain Daylight Time': 'MDT',
    'Pacific Standard Time': 'PST',
    'Pacific Daylight Time': 'PDT',
    'Alaska Standard Time': 'AKST',
    'Alaska Daylight Time': 'AKDT',
    'Hawaii-Aleutian Standard Time': 'HST',
    'Hawaii-Aleutian Daylight Time': 'HDT',
    'Atlantic Standard Time': 'AST',
    'Atlantic Daylight Time': 'ADT',
    'Newfoundland Standard Time': 'NST',
    'Newfoundland Daylight Time': 'NDT',
    'Greenwich Mean Time': 'GMT',
    'Coordinated Universal Time': 'UTC',
}


def abbreviate_tz_name(name: str) -> str:
    """Map a verbose timezone name (e.g. Windows' "Eastern Standard Time") to its abbreviation (EST).

    Already-abbreviated names (EST, UTC, GMT) pass through unchanged.
    """

    name = (name or '').strip()
    if not name:
        return ''
    upper = name.upper()
    if upper in {'UTC', 'GMT'}:
        return upper
    if name in _TZ_ABBR_MAP:
        return _TZ_ABBR_MAP[name]
    parts = [w for w in name.replace('-', ' ').split() if w]
    abbr = ''.join(p[0].upper() for p in parts)
    return abbr if 2 <= len(abbr) <= 5 else name


__all__ = [
    "humanize_relative",
    "format_local_hhmm",
    "format_display_datetime",
    "display_timezone_options",
    "get_display_timezone",
    "get_display_timezone_key",
    "minutes_since",
    "to_datetime",
    "abbreviate_tz_name",
    "DISPLAY_TIMEZONE_SETTING",
    "SYSTEM_TIMEZONE_KEY",
]
