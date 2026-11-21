from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtWidgets import QApplication

import modules.plannedtoolkit.services as services
from modules.plannedtoolkit.records import ScheduledItem
from modules.plannedtoolkit.schedule_controller import ScheduleController
from modules.plannedtoolkit.widgets.operational_timeline_widget import OperationalTimelineWidget

TODAY = date.today()
_FMT = "%Y-%m-%dT%H:%M:%S"


def _at(hour: int, minute: int = 0, day_offset: int = 0) -> str:
    return (datetime.combine(TODAY, datetime.min.time()) + timedelta(days=day_offset, hours=hour, minutes=minute)).strftime(_FMT)


def _item(id_, name, hour, *, status="Scheduled", kind="Milestone", assigned_to="", day_offset=0, **extra) -> ScheduledItem:
    return ScheduledItem(
        id=id_, name=name, kind=kind, starts_at=_at(hour, day_offset=day_offset),
        ends_at=_at(hour + 1, day_offset=day_offset), status=status, assigned_to=assigned_to, **extra,
    )


def _widget(monkeypatch, items: list[ScheduledItem]) -> tuple[QApplication, OperationalTimelineWidget, ScheduleController]:
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(services, "list_schedule_items", lambda incident_id=None: items)
    ctrl = ScheduleController("INC1")
    widget = OperationalTimelineWidget(ctrl)
    app.processEvents()
    return app, widget, ctrl


def test_empty_schedule_renders_now_marker_only(monkeypatch) -> None:
    _app, widget, _ctrl = _widget(monkeypatch, [])
    # On today with nothing scheduled, only the NOW marker row (if any) —
    # no crash, no stray activity rows.
    assert widget.table.rowCount() <= 1


def test_chronological_ordering_within_a_day(monkeypatch) -> None:
    items = [
        _item(1, "Later", 11),
        _item(2, "Earlier", 9),
        _item(3, "Middle", 10),
    ]
    _app, widget, _ctrl = _widget(monkeypatch, items)
    names = [
        widget.table.item(row, 1).text()
        for row in range(widget.table.rowCount())
        if widget.table.item(row, 1) is not None and widget.table.item(row, 1).text()
    ]
    assert names == ["Earlier", "Middle", "Later"]


def test_status_filter(monkeypatch) -> None:
    items = [
        _item(1, "Scheduled one", 9, status="Scheduled"),
        _item(2, "Delayed one", 10, status="Delayed"),
    ]
    _app, widget, _ctrl = _widget(monkeypatch, items)
    widget.status_filter_combo.setCurrentText("Delayed")
    visible = [
        widget.table.item(row, 1).text()
        for row in range(widget.table.rowCount())
        if widget.table.item(row, 1) is not None and widget.table.item(row, 1).text()
    ]
    assert visible == ["Delayed one"]


def test_date_navigation_shows_only_selected_date(monkeypatch) -> None:
    items = [
        _item(1, "Today", 9, day_offset=0),
        _item(2, "Tomorrow", 9, day_offset=1),
    ]
    _app, widget, _ctrl = _widget(monkeypatch, items)
    assert any(
        widget.table.item(row, 1) is not None and widget.table.item(row, 1).text() == "Today"
        for row in range(widget.table.rowCount())
    )
    widget._go_to(TODAY + timedelta(days=1))
    names = [
        widget.table.item(row, 1).text()
        for row in range(widget.table.rowCount())
        if widget.table.item(row, 1) is not None and widget.table.item(row, 1).text()
    ]
    assert names == ["Tomorrow"]


def test_overdue_activity_flagged_in_attention_column_without_status_change(monkeypatch) -> None:
    three_hours_ago = (datetime.now() - timedelta(hours=3)).strftime(_FMT)
    two_hours_ago = (datetime.now() - timedelta(hours=2)).strftime(_FMT)
    stuck = ScheduledItem(id=1, name="Stuck", kind="Milestone", starts_at=three_hours_ago, ends_at=two_hours_ago, status="Scheduled")
    items = [stuck]
    _app, widget, ctrl = _widget(monkeypatch, items)
    row = next(r for r in range(widget.table.rowCount()) if widget.table.item(r, 1) and widget.table.item(r, 1).text() == "Stuck")
    headers = [widget.table.horizontalHeaderItem(c).text() for c in range(widget.table.columnCount())]
    assert widget.table.item(row, headers.index("Attention")).text() == "Overdue"
    # Status must remain untouched -- the timeline never auto-changes it.
    assert ctrl.items()[0].status == "Scheduled"


def test_selecting_activity_resolves_correct_item(monkeypatch) -> None:
    items = [_item(1, "First", 9), _item(2, "Second", 10)]
    _app, widget, _ctrl = _widget(monkeypatch, items)
    second_row = next(r for r in range(widget.table.rowCount()) if widget.table.item(r, 1) and widget.table.item(r, 1).text() == "Second")
    widget.table.setCurrentCell(second_row, 0)
    selected = widget._selected_item()
    assert selected is not None
    assert selected.name == "Second"


def test_cancelled_activity_still_rendered(monkeypatch) -> None:
    items = [_item(1, "Called off", 9, status="Cancelled")]
    _app, widget, _ctrl = _widget(monkeypatch, items)
    names = [
        widget.table.item(row, 1).text()
        for row in range(widget.table.rowCount())
        if widget.table.item(row, 1) is not None and widget.table.item(row, 1).text()
    ]
    assert names == ["Called off"]


def test_refresh_reflects_backend_changes(monkeypatch) -> None:
    items = [_item(1, "Original", 9)]
    _app, widget, ctrl = _widget(monkeypatch, items)
    monkeypatch.setattr(services, "list_schedule_items", lambda incident_id=None: [_item(1, "Renamed", 9)])
    ctrl.refresh()
    names = [
        widget.table.item(row, 1).text()
        for row in range(widget.table.rowCount())
        if widget.table.item(row, 1) is not None and widget.table.item(row, 1).text()
    ]
    assert names == ["Renamed"]


def test_backward_compatible_with_minimal_legacy_item(monkeypatch) -> None:
    """A pre-Phase-1A/1C item with none of the new fields populated must
    render without crashing."""
    legacy = ScheduledItem(id=1, name="Legacy", starts_at=_at(9), status="Planned")
    _app, widget, _ctrl = _widget(monkeypatch, [legacy])
    assert widget.table.rowCount() >= 1
