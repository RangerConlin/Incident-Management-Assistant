from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TeamAlertState:
    emergency_flag: bool
    needs_assistance_flag: bool
    last_checkin_at: datetime | None
    team_status: str | None = None
    reference_time: datetime | None = None


@dataclass(frozen=True)
class CheckinThresholds:
    warning_minutes: int = 50
    overdue_minutes: int = 60


class AlertKind:
    NONE = "none"
    EMERGENCY = "emergency"
    NEEDS_ASSISTANCE = "assistance"
    CHECKIN_OVERDUE = "overdue"
    CHECKIN_WARNING = "warning"


_VALID_CHECKIN_STATUSES = {
    "enroute",
    "arrival",
    "returning to base",
    "at other location",
    "to other location",
    "find",
}


def _normalize_status(status: str | None) -> str:
    if not status:
        return ""
    lowered = str(status).lower()
    lowered = re.sub(r"[\-_/]+", " ", lowered)
    lowered = re.sub(r"[^0-9a-z\s]+", "", lowered)
    return " ".join(lowered.split())


def _is_checkin_status(status: str | None) -> bool:
    return _normalize_status(status) in _VALID_CHECKIN_STATUSES


def compute_alert_kind(
    state: TeamAlertState,
    *,
    now: datetime,
    thresholds: CheckinThresholds | None = None,
) -> str:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("`now` must be timezone-aware")
    thresholds = thresholds or CheckinThresholds()
    warning_minutes = max(0, int(thresholds.warning_minutes))
    overdue_minutes = max(warning_minutes, int(thresholds.overdue_minutes))

    if state.emergency_flag:
        return AlertKind.EMERGENCY
    if state.needs_assistance_flag:
        return AlertKind.NEEDS_ASSISTANCE
    if not _is_checkin_status(state.team_status):
        return AlertKind.NONE

    reference = state.last_checkin_at or state.reference_time
    if reference is None:
        logger.warning(
            "Team is in a timed status but missing last_checkin_at; defaulting to warning."
        )
        return AlertKind.CHECKIN_WARNING
    if reference.tzinfo is None or reference.utcoffset() is None:
        logger.debug(
            "Team last_checkin_at is naive; treating as overdue for safety."
        )
        return AlertKind.CHECKIN_OVERDUE

    elapsed_seconds = (now - reference).total_seconds()
    if elapsed_seconds < 0:
        return AlertKind.NONE

    elapsed_minutes = elapsed_seconds / 60.0
    if elapsed_minutes >= overdue_minutes:
        return AlertKind.CHECKIN_OVERDUE
    if elapsed_minutes >= warning_minutes:
        return AlertKind.CHECKIN_WARNING
    return AlertKind.NONE


def get_checkin_thresholds(settings_path: Path | None = None) -> CheckinThresholds:
    default = CheckinThresholds()
    path = settings_path or Path(__file__).resolve().parents[2] / "settings" / "team_alerts.json"
    if not path.exists():
        return default

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("Invalid JSON in %%s; using defaults", path)
        return default
    except OSError:
        logger.warning("Unable to read %%s; using defaults", path)
        return default

    def _coerce(value: Any, fallback: int) -> int:
        try:
            num = int(value)
        except (TypeError, ValueError):
            return fallback
        return max(0, num)

    warning = _coerce(raw.get("checkin_warning_minutes"), default.warning_minutes)
    overdue = _coerce(raw.get("checkin_overdue_minutes"), default.overdue_minutes)
    if overdue < warning:
        overdue = warning
    return CheckinThresholds(warning_minutes=warning, overdue_minutes=overdue)


__all__ = [
    "AlertKind",
    "CheckinThresholds",
    "TeamAlertState",
    "compute_alert_kind",
    "get_checkin_thresholds",
]
