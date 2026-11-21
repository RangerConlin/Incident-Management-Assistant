"""Configure one reminder (ScheduleTrigger) for an Event Schedule activity.

Phase 1D: reuses the existing shared notification/trigger infrastructure
end to end -- this dialog only builds the request body the existing
`/planned-meta/schedule-triggers` endpoints already accept (see
plannedtoolkit.py); it computes nothing itself except which of the three
modes (absolute / before-start / at-start) maps to which fields, and the
backend resolves a relative mode to an absolute `trigger_at` using the
activity's own planned time.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..records import ScheduledItem, ScheduleTrigger
from .schedule_time_utils import storage_dt, to_qdatetime

_MODE_SPECIFIC_TIME = "At a specific date/time"
_MODE_BEFORE_START = "A set time before planned start"
_MODE_AT_START = "At planned start"
_SEVERITIES = ("informational", "routine", "priority", "emergency")


class ReminderDialog(QDialog):
    def __init__(self, item: ScheduledItem, trigger: ScheduleTrigger | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Edit Reminder" if trigger else "Add Reminder")
        self.setMinimumWidth(420)
        self._item = item
        self._trigger = trigger
        self._build_ui()
        if trigger is not None:
            self._load(trigger)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText(self._item.name or "Reminder title")
        self.message_edit = QTextEdit()
        self.message_edit.setFixedHeight(60)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems([_MODE_BEFORE_START, _MODE_AT_START, _MODE_SPECIFIC_TIME])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)

        self.minutes_before_spin = QSpinBox()
        self.minutes_before_spin.setRange(1, 10080)  # up to a week
        self.minutes_before_spin.setValue(15)
        self.minutes_before_spin.setSuffix(" minutes before start")

        self.specific_time_edit = QDateTimeEdit()
        self.specific_time_edit.setCalendarPopup(True)
        self.specific_time_edit.setDisplayFormat("MM/dd/yyyy  HH:mm")
        self.specific_time_edit.setDateTime(to_qdatetime(self._item.starts_at))

        self.severity_combo = QComboBox()
        self.severity_combo.addItems(_SEVERITIES)
        self.severity_combo.setCurrentText("routine")

        self.audience_role_edit = QLineEdit()
        self.audience_role_edit.setPlaceholderText("Audience role (optional, e.g. Operations Section Chief)")
        self.audience_user_id_edit = QLineEdit()
        self.audience_user_id_edit.setPlaceholderText("Specific person record ID (optional)")

        form.addRow("Title", self.title_edit)
        form.addRow("Message", self.message_edit)
        form.addRow("When", self.mode_combo)
        form.addRow("", self.minutes_before_spin)
        form.addRow("", self.specific_time_edit)
        form.addRow("Severity", self.severity_combo)
        form.addRow("Audience Role", self.audience_role_edit)
        form.addRow("Audience Person", self.audience_user_id_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._on_mode_changed(self.mode_combo.currentText())

    def _on_mode_changed(self, mode: str) -> None:
        self.minutes_before_spin.setVisible(mode == _MODE_BEFORE_START)
        self.specific_time_edit.setVisible(mode == _MODE_SPECIFIC_TIME)

    def _load(self, trigger: ScheduleTrigger) -> None:
        self.title_edit.setText(trigger.title or trigger.label)
        self.message_edit.setPlainText(trigger.message_template or trigger.summary)
        if trigger.offset_minutes is not None and trigger.offset_minutes < 0:
            self.mode_combo.setCurrentText(_MODE_BEFORE_START)
            self.minutes_before_spin.setValue(abs(trigger.offset_minutes))
        elif trigger.offset_minutes == 0:
            self.mode_combo.setCurrentText(_MODE_AT_START)
        else:
            self.mode_combo.setCurrentText(_MODE_SPECIFIC_TIME)
            if trigger.trigger_at:
                self.specific_time_edit.setDateTime(to_qdatetime(trigger.trigger_at))
        if trigger.severity:
            self.severity_combo.setCurrentText(trigger.severity)
        self.audience_role_edit.setText(trigger.audience_role)
        self.audience_user_id_edit.setText(trigger.audience_user_id)
        self._on_mode_changed(self.mode_combo.currentText())

    def _on_accept(self) -> None:
        if not self.title_edit.text().strip() and not self._item.name:
            QMessageBox.warning(self, "Title required", "Enter a title for this reminder.")
            return
        self.accept()

    def values(self) -> dict[str, Any]:
        mode = self.mode_combo.currentText()
        payload: dict[str, Any] = {
            "schedule_item_id": self._item.record_id,
            "title": self.title_edit.text().strip() or self._item.name,
            "label": self.title_edit.text().strip() or self._item.name,
            "message_template": self.message_edit.toPlainText().strip(),
            "severity": self.severity_combo.currentText(),
            "audience_role": self.audience_role_edit.text().strip(),
            "audience_user_id": self.audience_user_id_edit.text().strip(),
        }
        if mode == _MODE_BEFORE_START:
            payload["offset_minutes"] = -int(self.minutes_before_spin.value())
            payload["relative_to"] = "start"
            payload["trigger_at"] = ""
        elif mode == _MODE_AT_START:
            payload["offset_minutes"] = 0
            payload["relative_to"] = "start"
            payload["trigger_at"] = ""
        else:
            payload["offset_minutes"] = None
            payload["trigger_at"] = storage_dt(self.specific_time_edit)
        return payload
