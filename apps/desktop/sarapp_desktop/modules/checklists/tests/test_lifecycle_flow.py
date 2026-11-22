from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

import modules.checklists.api as api
import modules.checklists.widgets.checklist_execution_widget as execution_module
from modules.checklists.widgets.checklist_execution_widget import ChecklistExecutionWidget


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _checklist(**overrides) -> dict:
    base = {
        "id": "c1",
        "int_id": 1,
        "incident_id": "INC1",
        "name": "Safety Check",
        "description": "",
        "instructions": "",
        "template_id": None,
        "owner_person_record": None,
        "linked_record": None,
        "status": "in_progress",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "created_by": 101,
        "completed_at": None,
        "completed_by": None,
        "archived_at": None,
        "archived_by": None,
        "lifecycle_event_seq": 0,
        "ics214_stream": None,
        "ics214_entry_id": None,
        "ics214_pending": False,
        "lifecycle_history": [],
        "sections": [],
    }
    base.update(overrides)
    return base


def _suppress_message_boxes(monkeypatch) -> None:
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))


def _load(widget: ChecklistExecutionWidget, checklist: dict, monkeypatch) -> None:
    import time

    app = _app()
    monkeypatch.setattr(api, "get_checklist", lambda incident_id, checklist_id: checklist)
    widget.load_checklist("INC1", checklist["id"])
    deadline = time.time() + 3
    while widget._checklist is None and time.time() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert widget._checklist is not None


class _FakeDialogAccept:
    """Stand-in for CompletionDialog/ReopenDialog: skips the real modal
    event loop (which would hang headless with no one to click it) while
    still returning whatever the test wants `acknowledge_failures()`/
    `selected_stream()`/`reason()` to be."""

    DialogCode = QDialog.DialogCode

    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def exec(self):
        return QDialog.DialogCode.Accepted

    def acknowledge_failures(self) -> bool:
        return True

    def selected_stream(self):
        return {"incident_wide": True}

    def reason(self) -> str:
        return "Needed to redo an item"


def test_complete_action_calls_api_with_dialog_choices_and_refreshes(monkeypatch) -> None:
    _app()
    monkeypatch.setattr(api, "current_actor_id", lambda: 101)
    monkeypatch.setattr(api, "resolve_person_display", lambda pr: f"P{pr}" if pr else "")
    _suppress_message_boxes(monkeypatch)
    widget = ChecklistExecutionWidget()
    _load(widget, _checklist(), monkeypatch)

    monkeypatch.setattr(api, "validate_completion", lambda incident_id, checklist_id: {
        "missing_required": [], "invalid_responses": [], "unresolved_failures": ["pfn"],
        "requires_acknowledgment": True, "ics214_stream_required": False,
    })
    monkeypatch.setattr(execution_module, "CompletionDialog", _FakeDialogAccept)

    captured = {}

    def fake_complete(incident_id, checklist_id, *, acknowledge_failures, stream):
        captured["args"] = (incident_id, checklist_id, acknowledge_failures, stream)
        return {
            "checklist": _checklist(status="completed", completed_by=101),
            "summary": {"answered_applicable_items": 3, "applicable_items": 3, "unresolved_failures": []},
            "ics214_entry_id": "e1",
            "ics214_pending": False,
        }

    monkeypatch.setattr(api, "complete_checklist", fake_complete)
    widget._on_complete_clicked()

    assert captured["args"] == ("INC1", "c1", True, {"incident_wide": True})


def test_complete_action_surfaces_conflict_error(monkeypatch) -> None:
    _app()
    from utils.api_client import APIError

    monkeypatch.setattr(api, "current_actor_id", lambda: 101)
    monkeypatch.setattr(api, "resolve_person_display", lambda pr: "")
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: warnings.append(a[2])))
    widget = ChecklistExecutionWidget()
    _load(widget, _checklist(), monkeypatch)

    monkeypatch.setattr(api, "validate_completion", lambda incident_id, checklist_id: {
        "missing_required": [], "invalid_responses": [], "unresolved_failures": [],
        "requires_acknowledgment": False, "ics214_stream_required": False,
    })
    monkeypatch.setattr(execution_module, "CompletionDialog", _FakeDialogAccept)

    def fake_complete(*args, **kwargs):
        raise APIError("This checklist was changed by another request", 409)

    monkeypatch.setattr(api, "complete_checklist", fake_complete)
    widget._on_complete_clicked()

    assert warnings and "changed by someone else" in warnings[0]


def test_reopen_action_calls_api_with_reason(monkeypatch) -> None:
    _app()
    monkeypatch.setattr(api, "current_actor_id", lambda: 101)
    monkeypatch.setattr(api, "resolve_person_display", lambda pr: "")
    _suppress_message_boxes(monkeypatch)
    widget = ChecklistExecutionWidget()
    _load(widget, _checklist(status="completed", completed_at="2026-01-01T00:00:00+00:00", completed_by=101), monkeypatch)

    monkeypatch.setattr(execution_module, "ReopenDialog", _FakeDialogAccept)
    monkeypatch.setattr(api, "get_checklist", lambda incident_id, checklist_id: _checklist(status="in_progress"))

    captured = {}

    def fake_reopen(incident_id, checklist_id, *, reason, stream):
        captured["args"] = (incident_id, checklist_id, reason, stream)
        return _checklist(status="in_progress")

    monkeypatch.setattr(api, "reopen_checklist", fake_reopen)
    widget._on_reopen_clicked()

    assert captured["args"] == ("INC1", "c1", "Needed to redo an item", {"incident_wide": True})


def test_archive_requires_confirmation(monkeypatch) -> None:
    _app()
    monkeypatch.setattr(api, "current_actor_id", lambda: 101)
    monkeypatch.setattr(api, "resolve_person_display", lambda pr: "")
    widget = ChecklistExecutionWidget()
    _load(widget, _checklist(), monkeypatch)

    archive_calls = []
    monkeypatch.setattr(api, "archive_checklist", lambda *a, **k: archive_calls.append(a))

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No))
    widget._on_archive_clicked()
    assert archive_calls == []

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    widget._on_archive_clicked()
    assert archive_calls == [("INC1", "c1")]


def test_actions_disabled_without_signed_in_actor(monkeypatch) -> None:
    _app()
    monkeypatch.setattr(api, "current_actor_id", lambda: None)
    monkeypatch.setattr(api, "resolve_person_display", lambda pr: "")
    widget = ChecklistExecutionWidget()
    _load(widget, _checklist(status="in_progress"), monkeypatch)

    assert widget.complete_button.isEnabled() is False
    assert widget.reopen_button.isEnabled() is False
    assert widget.archive_button.isEnabled() is False
    assert "Sign in" in widget.status_label.text()


def test_actions_enabled_appropriately_for_status(monkeypatch) -> None:
    _app()
    monkeypatch.setattr(api, "current_actor_id", lambda: 101)
    monkeypatch.setattr(api, "resolve_person_display", lambda pr: "")
    widget = ChecklistExecutionWidget()
    _load(widget, _checklist(status="archived"), monkeypatch)

    assert widget.complete_button.isEnabled() is False
    assert widget.reopen_button.isEnabled() is False
    assert widget.archive_button.isEnabled() is False  # already archived


def test_checklist_load_api_failure_shows_message(monkeypatch) -> None:
    _app()
    from utils.api_client import APIError

    def fake_get(incident_id, checklist_id):
        raise APIError("Checklist not found", 404)

    monkeypatch.setattr(api, "get_checklist", fake_get)
    widget = ChecklistExecutionWidget()
    widget.load_checklist("INC1", "missing")

    import time

    app = _app()
    deadline = time.time() + 3
    while "404" not in widget.status_label.text() and time.time() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert "404" in widget.status_label.text()
