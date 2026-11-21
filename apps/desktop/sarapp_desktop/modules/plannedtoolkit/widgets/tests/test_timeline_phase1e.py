from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtWidgets import QApplication

import modules.plannedtoolkit.services as services
import modules.plannedtoolkit.widgets.operational_timeline_widget as otw
from modules.plannedtoolkit.records import ScheduledItem
from modules.plannedtoolkit.schedule_controller import ScheduleController

TODAY = date.today()
_FMT = "%Y-%m-%dT%H:%M:%S"


def _at(hour: int) -> str:
    return (datetime.combine(TODAY, datetime.min.time()) + timedelta(hours=hour)).strftime(_FMT)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_status_filter_does_not_leak_stale_marker_row_data(monkeypatch) -> None:
    """Regression guard: a filter change that shrinks the row count used to
    leave a NOW-marker row's non-marker columns holding a previous render's
    item text (invisible due to the column span, but still present in the
    table model) -- found while hardening this phase."""
    _app()
    items = [
        ScheduledItem(id=1, name="Scheduled one", starts_at=_at(9), ends_at=_at(10), status="Scheduled"),
        ScheduledItem(id=2, name="Delayed one", starts_at=_at(10), ends_at=_at(11), status="Delayed"),
    ]
    monkeypatch.setattr(services, "list_schedule_items", lambda incident_id=None: items)
    monkeypatch.setattr(services, "list_schedule_triggers", lambda incident_id=None, schedule_item_id=None: [])
    ctrl = ScheduleController("INC1")
    widget = otw.OperationalTimelineWidget(ctrl)

    widget.status_filter_combo.setCurrentText("Delayed")

    visible_names = [
        widget.table.item(row, 1).text()
        for row in range(widget.table.rowCount())
        if widget.table.item(row, 1) is not None and widget.table.item(row, 1).text()
    ]
    assert visible_names == ["Delayed one"]

    # Every marker row's other columns must actually be empty, not just
    # visually hidden by the span.
    for row in range(widget.table.rowCount()):
        id_item = widget.table.item(row, 0)
        if id_item is not None and id_item.data(otw.Qt.ItemDataRole.UserRole) == "now_marker":
            for col in range(1, widget.table.columnCount()):
                cell = widget.table.item(row, col)
                assert cell is None or cell.text() == ""


def test_correct_button_reopens_terminal_activity(monkeypatch) -> None:
    item = ScheduledItem(id=1, record_id="R1", name="Done", status="Completed", revision=2)
    monkeypatch.setattr(services, "list_schedule_items", lambda incident_id=None: [item])
    monkeypatch.setattr(services, "list_schedule_triggers", lambda incident_id=None, schedule_item_id=None: [])
    calls = []
    monkeypatch.setattr(
        services, "correct_schedule_item",
        lambda rid, incident_id=None, **kw: calls.append((rid, kw)),
    )
    _app()
    ctrl = ScheduleController("INC1")
    dialog = otw.ActivityDetailDialog(item, ctrl)

    # The Correct action is always available, even on a terminal activity.
    assert dialog._correct_btn.isEnabled()
    # But routine actions are not.
    assert not dialog._start_btn.isEnabled()
    assert not dialog._complete_btn.isEnabled()

    from modules.plannedtoolkit.widgets.schedule_dialogs import CorrectionDialog

    correction = CorrectionDialog(item)
    correction.status_combo.setCurrentText("In Progress")
    correction.reason_edit.setPlainText("completed by mistake")
    values = correction.values()
    assert values == {"reason": "completed by mistake", "status": "In Progress"}

    assert ctrl.correct(item.id, expected_revision=item.revision, **values)
    assert len(calls) == 1
    rid, kwargs = calls[0]
    assert rid == 1
    assert kwargs["reason"] == "completed by mistake"
    assert kwargs["status"] == "In Progress"
    assert kwargs["expected_revision"] == 2


def test_correction_dialog_requires_reason(monkeypatch) -> None:
    _app()
    import modules.plannedtoolkit.widgets.schedule_dialogs as sd

    monkeypatch.setattr(sd.QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    item = ScheduledItem(id=1, record_id="R1", name="Done", status="Completed")
    dialog = sd.CorrectionDialog(item)
    dialog.status_combo.setCurrentText("Scheduled")
    dialog.reason_edit.setPlainText("")
    dialog._on_accept()
    # Still open (QDialog.Accepted not reached) because no reason was given.
    assert dialog.result() != dialog.DialogCode.Accepted


def test_correction_dialog_requires_at_least_one_change(monkeypatch) -> None:
    _app()
    import modules.plannedtoolkit.widgets.schedule_dialogs as sd

    monkeypatch.setattr(sd.QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    item = ScheduledItem(id=1, record_id="R1", name="Done", status="Completed")
    dialog = sd.CorrectionDialog(item)
    dialog.reason_edit.setPlainText("just a note, no change")
    dialog._on_accept()
    assert dialog.result() != dialog.DialogCode.Accepted
