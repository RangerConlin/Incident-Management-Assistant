"""Phase 4D: `modules.plannedtoolkit.checklist_links` registers the
Schedule Activity / Assignment / Operations Task handlers that
`modules.checklists.record_links` uses to render a checklist's
"Associated Records" list — verified here independently of the UI."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import modules.checklists.record_links as record_links
import modules.plannedtoolkit.checklist_links as checklist_links  # noqa: F401 - registers handlers
import modules.plannedtoolkit.services as services
from modules.plannedtoolkit.records import PlannedRecord, ScheduledItem


def test_handlers_are_registered() -> None:
    for record_type in ("planned_schedule_item", "planned_quick_assignment", "operations_task"):
        assert record_links.get_handler(record_type) is not None


def test_resolve_schedule_label_finds_matching_item(monkeypatch) -> None:
    item = ScheduledItem(id=1, record_id="INC1-PLAN-SCHEDULE-1", incident_id="INC1", name="Opening Ceremony")
    monkeypatch.setattr(services, "list_schedule_items", lambda incident_id: [item])
    label = record_links.describe("INC1", "planned_schedule_item", "INC1-PLAN-SCHEDULE-1")
    assert label == "Schedule Activity: Opening Ceremony"


def test_resolve_schedule_label_falls_back_to_id_when_not_found(monkeypatch) -> None:
    monkeypatch.setattr(services, "list_schedule_items", lambda incident_id: [])
    label = record_links.describe("INC1", "planned_schedule_item", "INC1-PLAN-SCHEDULE-99")
    assert label == "Schedule Activity: INC1-PLAN-SCHEDULE-99"


def test_resolve_assignment_label_finds_matching_record(monkeypatch) -> None:
    record = PlannedRecord(id=1, record_id="INC1-PLAN-QA-1", incident_id="INC1", title="Staff water station")
    monkeypatch.setattr(services, "list_records", lambda tool, incident_id: [record])
    label = record_links.describe("INC1", "planned_quick_assignment", "INC1-PLAN-QA-1")
    assert label == "Assignment: Staff water station"


def test_open_schedule_shows_message_when_record_missing(monkeypatch) -> None:
    from PySide6.QtWidgets import QApplication, QMessageBox

    QApplication.instance() or QApplication([])
    monkeypatch.setattr(services, "list_schedule_items", lambda incident_id: [])
    messages = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: messages.append(a[2])))
    record_links.open_record("INC1", "planned_schedule_item", "INC1-PLAN-SCHEDULE-1", None)
    assert messages and "no longer available" in messages[0]


def test_open_assignment_shows_message_when_record_missing(monkeypatch) -> None:
    from PySide6.QtWidgets import QApplication, QMessageBox

    QApplication.instance() or QApplication([])
    monkeypatch.setattr(services, "list_records", lambda tool, incident_id: [])
    messages = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: messages.append(a[2])))
    record_links.open_record("INC1", "planned_quick_assignment", "INC1-PLAN-QA-1", None)
    assert messages and "no longer available" in messages[0]
