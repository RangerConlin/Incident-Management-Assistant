from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialogButtonBox

import modules.checklists.api as api
from modules.checklists.widgets.lifecycle_dialogs import CompletionDialog, ReopenDialog


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


_CHECKLIST = {"name": "Safety Check", "incident_id": "INC1", "ics214_stream": None}


def test_completion_dialog_disables_ok_when_required_items_missing() -> None:
    _app()
    validation = {
        "missing_required": ["chk"],
        "invalid_responses": [],
        "unresolved_failures": [],
        "requires_acknowledgment": False,
        "ics214_stream_required": False,
    }
    dialog = CompletionDialog(_CHECKLIST, validation)
    assert dialog.buttons.button(QDialogButtonBox.Ok).isEnabled() is False


def test_completion_dialog_requires_explicit_acknowledgment_for_failures(monkeypatch) -> None:
    _app()
    monkeypatch.setattr(api, "list_stream_options", lambda incident_id: [])
    validation = {
        "missing_required": [],
        "invalid_responses": [],
        "unresolved_failures": ["pfn"],
        "requires_acknowledgment": True,
        "ics214_stream_required": False,
    }
    dialog = CompletionDialog(_CHECKLIST, validation)
    ok_button = dialog.buttons.button(QDialogButtonBox.Ok)
    assert ok_button.isEnabled() is False
    dialog.ack_check.setChecked(True)
    assert ok_button.isEnabled() is True
    assert dialog.acknowledge_failures() is True


def test_completion_dialog_requires_stream_selection_when_unresolved(monkeypatch) -> None:
    _app()
    monkeypatch.setattr(
        api, "list_stream_options", lambda incident_id: [{"label": "Operations Section", "stream": {"log_keys": ["operations_section"]}}]
    )
    validation = {
        "missing_required": [],
        "invalid_responses": [],
        "unresolved_failures": [],
        "requires_acknowledgment": False,
        "ics214_stream_required": True,
    }
    dialog = CompletionDialog(_CHECKLIST, validation)
    ok_button = dialog.buttons.button(QDialogButtonBox.Ok)
    assert ok_button.isEnabled() is False
    dialog.stream_combo.setCurrentIndex(1)
    assert ok_button.isEnabled() is True
    assert dialog.selected_stream() == {"log_keys": ["operations_section"]}


def test_completion_dialog_enabled_when_nothing_blocks() -> None:
    _app()
    validation = {
        "missing_required": [],
        "invalid_responses": [],
        "unresolved_failures": [],
        "requires_acknowledgment": False,
        "ics214_stream_required": False,
    }
    dialog = CompletionDialog(_CHECKLIST, validation)
    assert dialog.buttons.button(QDialogButtonBox.Ok).isEnabled() is True


def test_reopen_dialog_rejects_blank_reason() -> None:
    _app()
    dialog = ReopenDialog({**_CHECKLIST, "ics214_stream": {"incident_wide": True}})
    dialog.reason_edit.setPlainText("   ")
    dialog._on_accept()
    assert dialog.result() != dialog.DialogCode.Accepted


def test_reopen_dialog_accepts_with_reason_and_existing_stream() -> None:
    _app()
    dialog = ReopenDialog({**_CHECKLIST, "ics214_stream": {"incident_wide": True}})
    dialog.reason_edit.setPlainText("Found an error")
    dialog._on_accept()
    assert dialog.reason() == "Found an error"
    assert dialog.stream_combo is None  # stream already persisted, no picker needed
