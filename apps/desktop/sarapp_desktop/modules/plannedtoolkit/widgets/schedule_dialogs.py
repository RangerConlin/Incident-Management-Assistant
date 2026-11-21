"""Shared dialogs for the Event Schedule's views (Timeline + Activity List).

Kept in their own module so neither view file has to import the other —
both the Phase 1A/1B list and the Phase 1C timeline's activity-detail panel
reuse the same edit dialog and delay/cancel reason prompts rather than
each defining their own.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..records import ScheduledItem
from .schedule_time_utils import storage_dt, to_qdatetime

ACTIVITY_TYPE_PRESETS = (
    "Milestone", "Briefing", "Opening", "Closure", "Shift Change",
    "Inspection", "Performance", "Announcement", "Demobilization", "Other",
)


class ScheduleItemDialog(QDialog):
    """Create or edit an activity's planned details.

    Deliberately does not touch status/actual times/delay-cancel reasons —
    those are event-day actions with their own validated transitions, kept
    separate so this dialog can't put a record into an inconsistent state.
    """

    def __init__(self, item: ScheduledItem | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Edit Activity" if item else "New Activity")
        self.setMinimumWidth(420)
        self._item = item
        self._build_ui()
        if item is not None:
            self._load(item)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.kind_combo = QComboBox()
        self.kind_combo.setEditable(True)
        self.kind_combo.addItems(ACTIVITY_TYPE_PRESETS)

        self.starts_edit = QDateTimeEdit()
        self.starts_edit.setCalendarPopup(True)
        self.starts_edit.setDisplayFormat("MM/dd/yyyy  HH:mm")
        self.starts_edit.setDateTime(to_qdatetime(""))
        self.ends_edit = QDateTimeEdit()
        self.ends_edit.setCalendarPopup(True)
        self.ends_edit.setDisplayFormat("MM/dd/yyyy  HH:mm")
        self.ends_edit.setDateTime(self.starts_edit.dateTime().addSecs(1800))

        self.time_zone_edit = QLineEdit()
        self.time_zone_edit.setPlaceholderText("e.g. America/New_York")

        self.location_edit = QLineEdit()
        self.assigned_to_edit = QLineEdit()
        self.assigned_to_edit.setPlaceholderText("Responsible person or team (display name)")
        self.assigned_team_id_edit = QLineEdit()
        self.assigned_team_id_edit.setPlaceholderText("Team ID (optional)")
        self.assigned_person_id_edit = QLineEdit()
        self.assigned_person_id_edit.setPlaceholderText("Person record ID (optional)")
        self.meeting_id_edit = QLineEdit()
        self.meeting_id_edit.setPlaceholderText("Linked Meeting Planner ID (optional)")

        self.notes_edit = QTextEdit()
        self.notes_edit.setFixedHeight(70)

        form.addRow("Activity Name", self.name_edit)
        form.addRow("Activity Type", self.kind_combo)
        form.addRow("Planned Start", self.starts_edit)
        form.addRow("Planned End", self.ends_edit)
        form.addRow("Time Zone", self.time_zone_edit)
        form.addRow("Location", self.location_edit)
        form.addRow("Responsible", self.assigned_to_edit)
        form.addRow("Team ID", self.assigned_team_id_edit)
        form.addRow("Person ID", self.assigned_person_id_edit)
        form.addRow("Linked Meeting ID", self.meeting_id_edit)
        form.addRow("Notes", self.notes_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load(self, item: ScheduledItem) -> None:
        self.name_edit.setText(item.name)
        if item.kind:
            self.kind_combo.setCurrentText(item.kind)
        if item.starts_at:
            self.starts_edit.setDateTime(to_qdatetime(item.starts_at))
        if item.ends_at:
            self.ends_edit.setDateTime(to_qdatetime(item.ends_at))
        self.time_zone_edit.setText(item.time_zone)
        self.location_edit.setText(item.location)
        self.assigned_to_edit.setText(item.assigned_to)
        self.assigned_team_id_edit.setText(item.assigned_team_id)
        self.assigned_person_id_edit.setText(item.assigned_person_id)
        self.meeting_id_edit.setText(item.meeting_id)
        self.notes_edit.setPlainText(item.notes)

    def _on_accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Activity Name required", "Enter a name for this activity.")
            return
        if self.ends_edit.dateTime() < self.starts_edit.dateTime():
            QMessageBox.warning(self, "Invalid time range", "Planned end cannot be before planned start.")
            return
        self.accept()

    def values(self) -> dict[str, Any]:
        return {
            "name": self.name_edit.text().strip(),
            "kind": self.kind_combo.currentText().strip() or "Milestone",
            "starts_at": storage_dt(self.starts_edit),
            "ends_at": storage_dt(self.ends_edit),
            "time_zone": self.time_zone_edit.text().strip(),
            "location": self.location_edit.text().strip(),
            "assigned_to": self.assigned_to_edit.text().strip(),
            "assigned_team_id": self.assigned_team_id_edit.text().strip(),
            "assigned_person_id": self.assigned_person_id_edit.text().strip(),
            "meeting_id": self.meeting_id_edit.text().strip(),
            "notes": self.notes_edit.toPlainText().strip(),
        }


def prompt_delay_reason(parent: QWidget) -> str | None:
    reason, ok = QInputDialog.getMultiLineText(parent, "Mark Delayed", "Delay reason (required):")
    if not ok or not reason.strip():
        return None
    return reason.strip()


def prompt_cancellation_reason(parent: QWidget) -> str | None:
    reason, ok = QInputDialog.getMultiLineText(parent, "Cancel Activity", "Cancellation reason (required):")
    if not ok or not reason.strip():
        return None
    return reason.strip()
