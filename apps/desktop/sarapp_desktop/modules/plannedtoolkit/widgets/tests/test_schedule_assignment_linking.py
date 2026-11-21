"""Phase 2B: linking a Quick Assignment to an Event Schedule item."""
from __future__ import annotations

from PySide6.QtWidgets import QApplication, QDialog

import modules.plannedtoolkit.services as services
import modules.plannedtoolkit.widgets.operational_timeline_widget as otw
from modules.plannedtoolkit.records import PlannedRecord, ScheduledItem
from modules.plannedtoolkit.schedule_controller import ScheduleController
from modules.plannedtoolkit.widgets.assignment_detail_dialog import AssignmentDetailDialog


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


_SCHEDULE_ITEMS = [
    ScheduledItem(id=1, record_id="INC1-PLAN-SCHEDULE-1", name="Opening Briefing", starts_at="2026-12-01T09:00:00"),
    ScheduledItem(id=2, record_id="INC1-PLAN-SCHEDULE-2", name="Shift Change", starts_at="2026-12-01T18:00:00"),
]


def test_assignment_dialog_lists_schedule_items_with_no_selection_by_default(monkeypatch) -> None:
    _app()
    monkeypatch.setattr(services, "list_schedule_items", lambda incident_id=None: _SCHEDULE_ITEMS)

    dialog = AssignmentDetailDialog(incident_id="INC1", record=None)

    assert dialog.schedule_combo.count() == 3  # "None" + 2 items
    assert dialog.schedule_combo.currentData() == ""


def test_assignment_dialog_preselects_existing_records_linked_schedule_item(monkeypatch) -> None:
    _app()
    monkeypatch.setattr(services, "list_schedule_items", lambda incident_id=None: _SCHEDULE_ITEMS)
    record = PlannedRecord(id=5, record_id="INC1-PLAN-QA-5", title="Set up PA system", schedule_item_id="INC1-PLAN-SCHEDULE-2")

    dialog = AssignmentDetailDialog(incident_id="INC1", record=record)

    assert dialog.schedule_combo.currentData() == "INC1-PLAN-SCHEDULE-2"


def test_assignment_dialog_keeps_unresolved_linked_schedule_item_selectable(monkeypatch) -> None:
    _app()
    monkeypatch.setattr(services, "list_schedule_items", lambda incident_id=None: _SCHEDULE_ITEMS)
    record = PlannedRecord(id=5, record_id="INC1-PLAN-QA-5", title="Deleted link", schedule_item_id="INC1-PLAN-SCHEDULE-9")

    dialog = AssignmentDetailDialog(incident_id="INC1", record=record)

    assert dialog.schedule_combo.currentData() == "INC1-PLAN-SCHEDULE-9"


def test_assignment_dialog_save_includes_selected_schedule_item_id(monkeypatch) -> None:
    _app()
    monkeypatch.setattr(services, "list_schedule_items", lambda incident_id=None: _SCHEDULE_ITEMS)
    dialog = AssignmentDetailDialog(incident_id="INC1", record=None)
    dialog.title_edit.setText("Set up tables")
    index = dialog.schedule_combo.findData("INC1-PLAN-SCHEDULE-1")
    dialog.schedule_combo.setCurrentIndex(index)

    dialog._on_save()

    assert dialog.result_payload()["schedule_item_id"] == "INC1-PLAN-SCHEDULE-1"


def test_assignment_dialog_clear_schedule_item_removes_link_from_payload(monkeypatch) -> None:
    _app()
    monkeypatch.setattr(services, "list_schedule_items", lambda incident_id=None: _SCHEDULE_ITEMS)
    record = PlannedRecord(id=5, record_id="INC1-PLAN-QA-5", title="Set up PA system", schedule_item_id="INC1-PLAN-SCHEDULE-2")
    dialog = AssignmentDetailDialog(incident_id="INC1", record=record)

    dialog._clear_schedule_item()
    dialog._on_save()

    assert dialog.result_payload()["schedule_item_id"] == ""


def test_assignment_dialog_leaves_schedule_item_empty_when_not_provided(monkeypatch) -> None:
    _app()
    monkeypatch.setattr(services, "list_schedule_items", lambda incident_id=None: _SCHEDULE_ITEMS)
    dialog = AssignmentDetailDialog(incident_id="INC1", record=None)
    dialog.title_edit.setText("Untethered assignment")

    dialog._on_save()

    assert dialog.result_payload()["schedule_item_id"] == ""


def _controller(monkeypatch, items):
    monkeypatch.setattr(services, "list_schedule_items", lambda incident_id=None: items)
    monkeypatch.setattr(services, "list_schedule_triggers", lambda incident_id=None, schedule_item_id=None: [])
    return ScheduleController("INC1")


def test_activity_detail_lists_linked_assignments(monkeypatch) -> None:
    _app()
    item = ScheduledItem(id=1, record_id="INC1-PLAN-SCHEDULE-1", name="Opening", status="Scheduled")
    ctrl = _controller(monkeypatch, [item])
    linked = [
        PlannedRecord(id=10, record_id="INC1-PLAN-QA-10", title="Set up chairs", status="Planned", assigned_to="Alex", due_at="2026-12-01T08:00:00"),
    ]
    captured = {}

    def fake_list_records(tool, incident_id=None, *, status=None, search=None, schedule_item_id=None):
        captured["tool"] = tool
        captured["incident_id"] = incident_id
        captured["schedule_item_id"] = schedule_item_id
        return linked

    monkeypatch.setattr(services, "list_records", fake_list_records)

    dialog = otw.ActivityDetailDialog(item, ctrl)

    assert captured == {"tool": "quick-assignments", "incident_id": "INC1", "schedule_item_id": "INC1-PLAN-SCHEDULE-1"}
    assert dialog._linked_assignments_table.rowCount() == 1
    assert dialog._linked_assignments_table.item(0, 0).text() == "Set up chairs"
    assert dialog._linked_assignments_table.item(0, 2).text() == "Alex"


def test_activity_detail_add_assignment_links_new_record_to_the_activity(monkeypatch) -> None:
    _app()
    item = ScheduledItem(id=1, record_id="INC1-PLAN-SCHEDULE-1", name="Opening", status="Scheduled")
    ctrl = _controller(monkeypatch, [item])
    monkeypatch.setattr(services, "list_records", lambda *a, **k: [])
    created = {}

    def fake_create_record(tool, incident_id=None, **payload):
        created["tool"] = tool
        created["incident_id"] = incident_id
        created["payload"] = payload
        return PlannedRecord(id=99)

    monkeypatch.setattr(services, "create_record", fake_create_record)

    dialog = otw.ActivityDetailDialog(item, ctrl)

    def fake_exec(self):
        self.title_edit.setText("New linked assignment")
        self._on_save()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(AssignmentDetailDialog, "exec", fake_exec)
    dialog._add_linked_assignment()

    assert created["tool"] == "quick-assignments"
    assert created["payload"]["schedule_item_id"] == "INC1-PLAN-SCHEDULE-1"
    assert created["payload"]["title"] == "New linked assignment"
