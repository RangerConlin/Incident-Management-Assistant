"""Dialogs for the explicit Complete / Reopen lifecycle actions.

Both dialogs only ever *prepare* a request; the actual lifecycle call
(`api.complete_checklist`/`api.reopen_checklist`) is made by the execution
widget after the dialog is accepted, since that call must be able to
surface a backend error (a stale validation, a conflict, a stream the
backend still rejects) back into the same flow.
"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from .. import api


def _item_label(checklist: dict[str, Any], item_id: str) -> str:
    for section in checklist.get("sections") or []:
        for item in section.get("items") or []:
            if item.get("id") == item_id:
                return item.get("label") or item_id
    return item_id


class CompletionDialog(QDialog):
    """Stage 1 (validate-completion) rendered as a confirmation dialog.

    ``can_complete`` reflects the *checklist's* response-completeness
    (missing required / invalid responses) — unresolved failures never
    block completion by themselves, they only require the explicit
    acknowledgment checkbox below to be checked before this dialog can be
    accepted.
    """

    def __init__(self, checklist: dict[str, Any], validation: dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Complete Checklist")
        self.resize(480, 420)
        self._validation = validation
        self._stream_options: list[dict[str, Any]] = []

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>{checklist.get('name', '')}</b>"))

        blocking = list(validation.get("missing_required") or []) + list(validation.get("invalid_responses") or [])
        if blocking:
            layout.addWidget(QLabel("The following items must be answered before this checklist can be completed:"))
            problems = QListWidget()
            for item_id in blocking:
                problems.addItem(QListWidgetItem(_item_label(checklist, item_id)))
            layout.addWidget(problems)

        self.ack_check: Optional[QCheckBox] = None
        failures = validation.get("unresolved_failures") or []
        if failures and not blocking:
            layout.addWidget(QLabel(f"This checklist has {len(failures)} unresolved failed check(s):"))
            failure_list = QListWidget()
            for item_id in failures:
                failure_list.addItem(QListWidgetItem(_item_label(checklist, item_id)))
            layout.addWidget(failure_list)
            self.ack_check = QCheckBox("I acknowledge these unresolved failures and want to complete anyway.")
            self.ack_check.toggled.connect(self._refresh_ok_enabled)
            layout.addWidget(self.ack_check)

        self.stream_combo: Optional[QComboBox] = None
        if not blocking and validation.get("ics214_stream_required"):
            layout.addWidget(QLabel("Select the ICS-214 stream to receive this completion entry:"))
            self.stream_combo = QComboBox()
            self.stream_combo.addItem("Select a stream…", None)
            incident_id = checklist.get("incident_id")
            if incident_id:
                try:
                    self._stream_options = api.list_stream_options(incident_id)
                except Exception:
                    self._stream_options = []
            for option in self._stream_options:
                self.stream_combo.addItem(option["label"], option["stream"])
            self.stream_combo.currentIndexChanged.connect(self._refresh_ok_enabled)
            layout.addWidget(self.stream_combo)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        if blocking:
            self.buttons.button(QDialogButtonBox.Ok).setEnabled(False)
        else:
            self._refresh_ok_enabled()

    def _refresh_ok_enabled(self, *_args: Any) -> None:
        ok = True
        if self.ack_check is not None and not self.ack_check.isChecked():
            ok = False
        if self.stream_combo is not None and self.stream_combo.currentData() is None:
            ok = False
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(ok)

    def acknowledge_failures(self) -> bool:
        return bool(self.ack_check and self.ack_check.isChecked())

    def selected_stream(self) -> Optional[dict[str, Any]]:
        return self.stream_combo.currentData() if self.stream_combo is not None else None


class ReopenDialog(QDialog):
    def __init__(self, checklist: dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Reopen Checklist")
        self.resize(420, 320)
        self._stream_options: list[dict[str, Any]] = []

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Reopen <b>{checklist.get('name', '')}</b>?"))
        layout.addWidget(QLabel("Reason for reopening (required):"))
        self.reason_edit = QPlainTextEdit()
        self.reason_edit.setFixedHeight(80)
        layout.addWidget(self.reason_edit)

        self.stream_combo: Optional[QComboBox] = None
        if not checklist.get("ics214_stream"):
            layout.addWidget(QLabel("Select the ICS-214 stream to receive this entry:"))
            self.stream_combo = QComboBox()
            self.stream_combo.addItem("Select a stream…", None)
            incident_id = checklist.get("incident_id")
            if incident_id:
                try:
                    self._stream_options = api.list_stream_options(incident_id)
                except Exception:
                    self._stream_options = []
            for option in self._stream_options:
                self.stream_combo.addItem(option["label"], option["stream"])
            layout.addWidget(self.stream_combo)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _on_accept(self) -> None:
        if not self.reason_edit.toPlainText().strip():
            self.reason_edit.setPlaceholderText("A reason is required.")
            return
        if self.stream_combo is not None and self.stream_combo.currentData() is None:
            return
        self.accept()

    def reason(self) -> str:
        return self.reason_edit.toPlainText().strip()

    def selected_stream(self) -> Optional[dict[str, Any]]:
        return self.stream_combo.currentData() if self.stream_combo is not None else None


__all__ = ["CompletionDialog", "ReopenDialog"]
