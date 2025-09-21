from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
import sys
from pathlib import Path


MODULE_NAME = "modules.operations.panels.team_alerts"
MODULE_PATH = Path(__file__).resolve().parents[1] / "modules/operations/panels/team_alerts.py"

spec = importlib.util.spec_from_file_location(MODULE_NAME, MODULE_PATH)
assert spec and spec.loader
team_alerts = importlib.util.module_from_spec(spec)
sys.modules[MODULE_NAME] = team_alerts
spec.loader.exec_module(team_alerts)

AlertKind = team_alerts.AlertKind
TeamAlertState = team_alerts.TeamAlertState
CheckinThresholds = team_alerts.CheckinThresholds
compute_alert_kind = team_alerts.compute_alert_kind


NOW = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)


def _aware(minutes_ago: float) -> datetime:
    return NOW - timedelta(minutes=minutes_ago)


def test_emergency_overrides_other_flags() -> None:
    state = TeamAlertState(
        emergency_flag=True,
        needs_assistance_flag=True,
        last_checkin_at=_aware(10),
        team_status="enroute",
    )
    assert compute_alert_kind(state, now=NOW) == AlertKind.EMERGENCY


def test_needs_assistance_when_no_emergency() -> None:
    state = TeamAlertState(
        emergency_flag=False,
        needs_assistance_flag=True,
        last_checkin_at=_aware(70),
        team_status="arrival",
    )
    assert compute_alert_kind(state, now=NOW) == AlertKind.NEEDS_ASSISTANCE


def test_ineligible_status_suppresses_time_alerts() -> None:
    state = TeamAlertState(
        emergency_flag=False,
        needs_assistance_flag=False,
        last_checkin_at=_aware(70),
        team_status="Staged",
    )
    assert compute_alert_kind(state, now=NOW) == AlertKind.NONE


def test_overdue_when_elapsed_exceeds_threshold() -> None:
    state = TeamAlertState(
        emergency_flag=False,
        needs_assistance_flag=False,
        last_checkin_at=_aware(61),
        team_status="enroute",
    )
    assert compute_alert_kind(state, now=NOW) == AlertKind.CHECKIN_OVERDUE


def test_warning_when_elapsed_exceeds_warning_threshold() -> None:
    state = TeamAlertState(
        emergency_flag=False,
        needs_assistance_flag=False,
        last_checkin_at=_aware(55),
        team_status="arrival",
    )
    assert compute_alert_kind(state, now=NOW) == AlertKind.CHECKIN_WARNING


def test_no_alert_when_recent_checkin() -> None:
    state = TeamAlertState(
        emergency_flag=False,
        needs_assistance_flag=False,
        last_checkin_at=_aware(10),
        team_status="Returning to Base",
    )
    assert compute_alert_kind(state, now=NOW) == AlertKind.NONE


def test_naive_timestamp_treated_as_overdue() -> None:
    naive_time = datetime(2024, 1, 1, 10, 30)  # naive timestamp
    state = TeamAlertState(
        emergency_flag=False,
        needs_assistance_flag=False,
        last_checkin_at=naive_time,
        team_status="Find",
    )
    assert compute_alert_kind(state, now=NOW) == AlertKind.CHECKIN_OVERDUE


def test_missing_checkin_uses_reference_time() -> None:
    state = TeamAlertState(
        emergency_flag=False,
        needs_assistance_flag=False,
        last_checkin_at=None,
        team_status="To Other Location",
        reference_time=_aware(75),
    )
    assert compute_alert_kind(state, now=NOW) == AlertKind.CHECKIN_OVERDUE


def test_boundary_minutes() -> None:
    thresholds = CheckinThresholds(warning_minutes=50, overdue_minutes=60)
    warning_state = TeamAlertState(
        emergency_flag=False,
        needs_assistance_flag=False,
        last_checkin_at=_aware(50),
        team_status="arrival",
    )
    overdue_state = TeamAlertState(
        emergency_flag=False,
        needs_assistance_flag=False,
        last_checkin_at=_aware(60),
        team_status="arrival",
    )
    assert (
        compute_alert_kind(warning_state, now=NOW, thresholds=thresholds)
        == AlertKind.CHECKIN_WARNING
    )
    assert (
        compute_alert_kind(overdue_state, now=NOW, thresholds=thresholds)
        == AlertKind.CHECKIN_OVERDUE
    )


def test_status_normalization_with_whitespace() -> None:
    state = TeamAlertState(
        emergency_flag=False,
        needs_assistance_flag=False,
        last_checkin_at=_aware(55),
        team_status="  returning   to   base  ",
    )
    assert compute_alert_kind(state, now=NOW) == AlertKind.CHECKIN_WARNING
