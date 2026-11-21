from __future__ import annotations

from PySide6.QtWidgets import QApplication

import modules.plannedtoolkit.services as services
import modules.plannedtoolkit.widgets.operational_timeline_widget as otw
import modules.plannedtoolkit.widgets.schedule_dialogs as sd
from modules.plannedtoolkit.records import ScheduledItem, ScheduleTrigger
from modules.plannedtoolkit.schedule_controller import ScheduleController
from modules.plannedtoolkit.widgets.reminder_dialog import ReminderDialog


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _controller(monkeypatch, items):
    monkeypatch.setattr(services, "list_schedule_items", lambda incident_id=None: items)
    monkeypatch.setattr(services, "list_schedule_triggers", lambda incident_id=None, schedule_item_id=None: [])
    return ScheduleController("INC1")


def test_schedule_item_dialog_loads_linked_meeting_and_gis_into_combos(monkeypatch) -> None:
    _app()
    monkeypatch.setattr(sd, "list_meetings", lambda incident_id: [{"id": 1, "title": "Staff Mtg", "meeting_date": "2026-12-01"}])
    monkeypatch.setattr(sd, "list_gis_features", lambda incident_id: [{"id": 5, "label": "Main Gate", "feature_type": "point"}])
    item = ScheduledItem(id=1, record_id="R1", name="Opening", starts_at="2026-12-01T09:00:00", meeting_id="1", gis_feature_id="5")

    dialog = sd.ScheduleItemDialog(item, incident_id="INC1")
    assert dialog.meeting_combo.currentData() == "1"
    assert dialog.gis_combo.currentData() == "5"


def test_schedule_item_dialog_defaults_end_time_from_loaded_start_when_unset(monkeypatch) -> None:
    """Regression guard for a bug found during Phase 1D integration: the End
    field must derive from the item's actual loaded start, not whatever
    wall-clock time the dialog happened to be built at."""
    _app()
    monkeypatch.setattr(sd, "list_meetings", lambda incident_id: [])
    monkeypatch.setattr(sd, "list_gis_features", lambda incident_id: [])
    item = ScheduledItem(id=1, record_id="R1", name="Opening", starts_at="2026-12-01T09:00:00", ends_at="")

    dialog = sd.ScheduleItemDialog(item, incident_id="INC1")
    assert dialog.values()["ends_at"] == "2026-12-01T09:30:00"


def test_schedule_item_dialog_preserves_stored_end_time(monkeypatch) -> None:
    _app()
    monkeypatch.setattr(sd, "list_meetings", lambda incident_id: [])
    monkeypatch.setattr(sd, "list_gis_features", lambda incident_id: [])
    item = ScheduledItem(id=1, record_id="R1", name="Opening", starts_at="2026-12-01T09:00:00", ends_at="2026-12-01T11:00:00")

    dialog = sd.ScheduleItemDialog(item, incident_id="INC1")
    assert dialog.values()["ends_at"] == "2026-12-01T11:00:00"


def test_activity_detail_shows_resolved_meeting_and_gis_labels(monkeypatch) -> None:
    _app()
    monkeypatch.setattr(otw, "resolve_meeting", lambda incident_id, mid: {"title": "Staff Mtg", "meeting_date": "2026-12-01"} if mid else None)
    monkeypatch.setattr(otw, "resolve_gis_feature", lambda incident_id, fid: {"label": "Main Gate", "feature_type": "point"} if fid else None)
    item = ScheduledItem(id=1, record_id="R1", name="Opening", status="Scheduled", meeting_id="1", gis_feature_id="5")
    ctrl = _controller(monkeypatch, [item])

    dialog = otw.ActivityDetailDialog(item, ctrl)
    assert "Staff Mtg" in dialog._meeting_label.text()
    assert "Main Gate" in dialog._gis_label.text()
    assert dialog._meeting_open_btn.isEnabled()


def test_activity_detail_handles_missing_linked_records_gracefully(monkeypatch) -> None:
    _app()
    monkeypatch.setattr(otw, "resolve_meeting", lambda incident_id, mid: None)
    monkeypatch.setattr(otw, "resolve_gis_feature", lambda incident_id, fid: None)
    item = ScheduledItem(id=1, record_id="R1", name="Opening", status="Scheduled", meeting_id="999", gis_feature_id="888")
    ctrl = _controller(monkeypatch, [item])

    dialog = otw.ActivityDetailDialog(item, ctrl)
    assert dialog._meeting_label.text() == "(meeting not found)"
    assert dialog._gis_label.text() == "(location not found)"
    # Even an unresolved link can still be cleared.
    assert dialog._meeting_unlink_btn.isEnabled()
    assert dialog._gis_unlink_btn.isEnabled()
    # But there is nothing to navigate to.
    assert not dialog._meeting_open_btn.isEnabled()


def test_activity_detail_with_no_links_shows_placeholders_and_offers_create(monkeypatch) -> None:
    _app()
    item = ScheduledItem(id=1, record_id="R1", name="Opening", status="Scheduled")
    ctrl = _controller(monkeypatch, [item])

    dialog = otw.ActivityDetailDialog(item, ctrl)
    assert dialog._meeting_label.text() == "—"
    assert not dialog._meeting_unlink_btn.isEnabled()
    assert dialog._qa_create_btn.isEnabled()
    assert not dialog._qa_unlink_btn.isEnabled()


def test_activity_detail_with_linked_quick_assignment_disables_create(monkeypatch) -> None:
    _app()
    item = ScheduledItem(id=1, record_id="R1", name="Opening", status="Scheduled", quick_assignment_id="R2")
    ctrl = _controller(monkeypatch, [item])

    dialog = otw.ActivityDetailDialog(item, ctrl)
    assert dialog._qa_label.text() == "R2"
    assert not dialog._qa_create_btn.isEnabled()
    assert dialog._qa_unlink_btn.isEnabled()


def test_activity_detail_unlink_meeting_clears_only_the_schedule_items_own_field(monkeypatch) -> None:
    _app()
    item = ScheduledItem(id=1, record_id="R1", name="Opening", status="Scheduled", meeting_id="1")
    ctrl = _controller(monkeypatch, [item])
    calls = []
    monkeypatch.setattr(services, "update_schedule_item", lambda rid, patch, incident_id=None: calls.append((rid, patch)))

    dialog = otw.ActivityDetailDialog(item, ctrl)
    dialog._unlink_meeting()
    assert calls == [(1, {"meeting_id": "", "expected_revision": 0})]


def test_reminders_table_shows_delivery_state(monkeypatch) -> None:
    _app()
    item = ScheduledItem(id=1, record_id="R1", name="Opening", status="Scheduled")
    fired = ScheduleTrigger(id=1, trigger_id="T1", title="Fired one", trigger_at="2026-01-01T00:00:00", fired_at="2026-01-01T00:00:05")
    pending = ScheduleTrigger(id=2, trigger_id="T2", title="Pending one", trigger_at="2099-01-01T00:00:00", enabled=True)
    monkeypatch.setattr(services, "list_schedule_items", lambda incident_id=None: [item])
    monkeypatch.setattr(services, "list_schedule_triggers", lambda incident_id=None, schedule_item_id=None: [fired, pending])
    ctrl = ScheduleController("INC1")

    dialog = otw.ActivityDetailDialog(item, ctrl)
    assert dialog._reminders_table.rowCount() == 2
    states = {dialog._reminders_table.item(r, 1).text(): dialog._reminders_table.item(r, 3).text() for r in range(2)}
    assert states["Fired one"] == "Delivered"
    assert states["Pending one"] == "Enabled"


def test_edit_reminder_blocked_once_fired(monkeypatch) -> None:
    _app()
    item = ScheduledItem(id=1, record_id="R1", name="Opening", status="Scheduled")
    fired = ScheduleTrigger(id=1, trigger_id="T1", title="Fired one", fired_at="2026-01-01T00:00:05")
    monkeypatch.setattr(services, "list_schedule_items", lambda incident_id=None: [item])
    monkeypatch.setattr(services, "list_schedule_triggers", lambda incident_id=None, schedule_item_id=None: [fired])
    update_calls = []
    monkeypatch.setattr(services, "update_schedule_trigger", lambda rid, patch, incident_id=None: update_calls.append(rid))
    # The "already fired, can't edit" path shows a blocking QMessageBox;
    # stub it out so the test doesn't wait on a click that never comes.
    monkeypatch.setattr(otw.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    ctrl = ScheduleController("INC1")

    dialog = otw.ActivityDetailDialog(item, ctrl)
    dialog._reminders_table.setCurrentCell(0, 0)
    dialog._edit_reminder()
    assert update_calls == []  # editing a fired trigger is a no-op, not an update call


def test_reminder_dialog_before_start_mode_sets_negative_offset() -> None:
    _app()
    item = ScheduledItem(id=1, record_id="R1", name="Briefing", starts_at="2026-12-01T09:00:00")
    dialog = ReminderDialog(item)
    dialog.minutes_before_spin.setValue(20)
    values = dialog.values()
    assert values["offset_minutes"] == -20
    assert values["relative_to"] == "start"
    assert values["trigger_at"] == ""
    assert values["schedule_item_id"] == "R1"


def test_reminder_dialog_loads_existing_trigger_for_edit() -> None:
    _app()
    item = ScheduledItem(id=1, record_id="R1", name="Briefing", starts_at="2026-12-01T09:00:00")
    trigger = ScheduleTrigger(
        id=1, trigger_id="T1", title="Reminder", severity="priority",
        offset_minutes=-10, relative_to="start", audience_role="Logistics",
    )
    dialog = ReminderDialog(item, trigger=trigger)
    assert dialog.minutes_before_spin.value() == 10
    assert dialog.severity_combo.currentText() == "priority"
    assert dialog.audience_role_edit.text() == "Logistics"
