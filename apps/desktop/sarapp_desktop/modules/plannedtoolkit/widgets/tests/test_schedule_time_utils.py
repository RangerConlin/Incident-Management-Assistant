from __future__ import annotations

from datetime import datetime

from modules.plannedtoolkit.widgets.schedule_time_utils import (
    friendly_dt,
    friendly_time,
    is_overdue,
    minutes_diff,
    parse_dt,
    planned_vs_actual_text,
)


def test_parse_dt_accepts_plain_iso_and_z_suffix() -> None:
    assert parse_dt("2026-12-01T09:00:00") == datetime(2026, 12, 1, 9, 0, 0)
    assert parse_dt("2026-12-01T09:00:00Z").replace(tzinfo=None) == datetime(2026, 12, 1, 9, 0, 0)


def test_parse_dt_returns_none_for_empty_or_invalid() -> None:
    assert parse_dt("") is None
    assert parse_dt("not-a-date") is None


def test_friendly_dt_and_friendly_time() -> None:
    assert friendly_dt("2026-12-01T09:05:00") == "Dec 01  09:05"
    assert friendly_time("2026-12-01T09:05:00") == "09:05"
    assert friendly_dt("") == ""
    assert friendly_time("") == ""


def test_minutes_diff() -> None:
    assert minutes_diff("2026-12-01T09:00:00", "2026-12-01T09:08:00") == 8
    assert minutes_diff("2026-12-01T09:00:00", "2026-12-01T08:52:00") == -8
    assert minutes_diff("2026-12-01T09:00:00", "") is None
    assert minutes_diff("", "2026-12-01T09:00:00") is None


def test_planned_vs_actual_text_started_late_and_early() -> None:
    assert planned_vs_actual_text(
        "2026-12-01T09:00:00", "2026-12-01T09:30:00", "2026-12-01T09:08:00", ""
    ) == "Started 8 min late"
    assert planned_vs_actual_text(
        "2026-12-01T09:00:00", "2026-12-01T09:30:00", "2026-12-01T08:55:00", ""
    ) == "Started 5 min early"
    assert planned_vs_actual_text(
        "2026-12-01T09:00:00", "2026-12-01T09:30:00", "2026-12-01T09:00:00", ""
    ) == "Started on schedule"


def test_planned_vs_actual_text_prefers_finish_once_actual_end_known() -> None:
    assert planned_vs_actual_text(
        "2026-12-01T09:00:00", "2026-12-01T09:30:00", "2026-12-01T08:55:00", "2026-12-01T09:18:00"
    ) == "Finished 12 min early"
    assert planned_vs_actual_text(
        "2026-12-01T09:00:00", "2026-12-01T09:30:00", "2026-12-01T09:00:00", "2026-12-01T09:45:00"
    ) == "Finished 15 min late"


def test_planned_vs_actual_text_blank_when_no_actual_times() -> None:
    assert planned_vs_actual_text("2026-12-01T09:00:00", "2026-12-01T09:30:00", "", "") == ""


def test_is_overdue_true_for_open_status_past_due() -> None:
    now = datetime(2026, 12, 1, 10, 0, 0)
    assert is_overdue("Scheduled", "2026-12-01T08:00:00", "2026-12-01T09:00:00", now=now) is True
    assert is_overdue("In Progress", "2026-12-01T08:00:00", "2026-12-01T09:00:00", now=now) is True
    assert is_overdue("Delayed", "2026-12-01T08:00:00", "2026-12-01T09:00:00", now=now) is True


def test_is_overdue_false_for_terminal_status_or_future() -> None:
    now = datetime(2026, 12, 1, 10, 0, 0)
    assert is_overdue("Completed", "2026-12-01T08:00:00", "2026-12-01T09:00:00", now=now) is False
    assert is_overdue("Cancelled", "2026-12-01T08:00:00", "2026-12-01T09:00:00", now=now) is False
    assert is_overdue("Scheduled", "2026-12-01T11:00:00", "2026-12-01T12:00:00", now=now) is False
