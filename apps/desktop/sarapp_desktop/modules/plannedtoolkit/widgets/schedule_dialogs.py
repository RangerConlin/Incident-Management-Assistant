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

from ..record_resolvers import list_gis_features, list_meetings
from ..records import ScheduledItem
from .schedule_time_utils import storage_dt, to_qdatetime
from .team_picker import TeamPicker
from modules.logistics.facilities.widgets.personnel_picker import PersonnelPicker

ACTIVITY_TYPE_PRESETS = (
    "Milestone", "Briefing", "Opening", "Closure", "Shift Change",
    "Inspection", "Performance", "Announcement", "Demobilization", "Other",
)
_NONE_LABEL = "— None —"


class ScheduleItemDialog(QDialog):
    """Create or edit an activity's planned details, including its links to
    an existing Meeting, GIS location, Personnel record, and/or Team.

    Deliberately does not touch status/actual times/delay-cancel reasons —
    those are event-day actions with their own validated transitions, kept
    separate so this dialog can't put a record into an inconsistent state.
    It also never touches `quick_assignment_id` — that link is set only via
    the Activity Detail panel's link/create actions, not by editing planned
    details.
    """

    def __init__(self, item: ScheduledItem | None = None, incident_id: str | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Edit Activity" if item else "New Activity")
        self.setMinimumWidth(460)
        self._item = item
        self.incident_id = incident_id
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
        self.location_edit.setPlaceholderText("Plain-text location (used unless a GIS location is linked below)")

        self.assigned_to_edit = QLineEdit()
        self.assigned_to_edit.setPlaceholderText("Responsible person or team (display name)")
        self.person_picker = PersonnelPicker()
        self.person_picker.personnelSelected.connect(self._on_person_selected)
        self.team_picker = TeamPicker(self.incident_id)
        self.team_picker.teamSelected.connect(self._on_team_selected)

        self.meeting_combo = QComboBox()
        self._populate_meeting_combo()
        self.gis_combo = QComboBox()
        self._populate_gis_combo()

        self.notes_edit = QTextEdit()
        self.notes_edit.setFixedHeight(70)

        form.addRow("Activity Name", self.name_edit)
        form.addRow("Activity Type", self.kind_combo)
        form.addRow("Planned Start", self.starts_edit)
        form.addRow("Planned End", self.ends_edit)
        form.addRow("Time Zone", self.time_zone_edit)
        form.addRow("Location", self.location_edit)
        form.addRow("Linked GIS Location", self.gis_combo)
        form.addRow("Responsible (display)", self.assigned_to_edit)
        form.addRow("— or Personnel", self.person_picker)
        form.addRow("— or Team", self.team_picker)
        form.addRow("Linked Meeting", self.meeting_combo)
        form.addRow("Notes", self.notes_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate_meeting_combo(self) -> None:
        self.meeting_combo.clear()
        self.meeting_combo.addItem(_NONE_LABEL, "")
        for meeting in list_meetings(self.incident_id or ""):
            label = f"{meeting.get('title', '')} ({meeting.get('meeting_date', '')})"
            self.meeting_combo.addItem(label, str(meeting.get("id") or ""))

    def _populate_gis_combo(self) -> None:
        self.gis_combo.clear()
        self.gis_combo.addItem(_NONE_LABEL, "")
        for feature in list_gis_features(self.incident_id or ""):
            label = f"{feature.get('label', '')} ({feature.get('feature_type', '')})"
            self.gis_combo.addItem(label, str(feature.get("id") or ""))

    def _select_combo_by_data(self, combo: QComboBox, value: str) -> None:
        if not value:
            combo.setCurrentIndex(0)
            return
        index = combo.findData(value)
        if index < 0:
            # Linked record no longer resolves (deleted/unavailable) --
            # keep the stored id selectable rather than silently dropping
            # the link the user didn't ask to remove.
            combo.addItem(f"(unavailable) {value}", value)
            index = combo.count() - 1
        combo.setCurrentIndex(index)

    def _on_person_selected(self, person_id: object, name: str) -> None:
        if person_id:
            self.assigned_to_edit.setText(name)

    def _on_team_selected(self, team_id: object, name: str) -> None:
        if team_id:
            self.assigned_to_edit.setText(name)

    def _load(self, item: ScheduledItem) -> None:
        self.name_edit.setText(item.name)
        if item.kind:
            self.kind_combo.setCurrentText(item.kind)
        if item.starts_at:
            self.starts_edit.setDateTime(to_qdatetime(item.starts_at))
        if item.ends_at:
            self.ends_edit.setDateTime(to_qdatetime(item.ends_at))
        elif item.starts_at:
            # No stored end time -- derive the displayed default from the
            # item's actual loaded start rather than leaving the stale
            # "now + 30 min" default _build_ui() set before _load() ran.
            self.ends_edit.setDateTime(self.starts_edit.dateTime().addSecs(1800))
        self.time_zone_edit.setText(item.time_zone)
        self.location_edit.setText(item.location)
        self.assigned_to_edit.setText(item.assigned_to)
        self.person_picker.set_value(item.assigned_person_id, item.assigned_to if item.assigned_person_id else "")
        self.team_picker.set_value(item.assigned_team_id, item.assigned_to if item.assigned_team_id else "")
        self._select_combo_by_data(self.meeting_combo, item.meeting_id)
        self._select_combo_by_data(self.gis_combo, item.gis_feature_id)
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
            "assigned_team_id": self.team_picker.team_id,
            "assigned_person_id": self.person_picker.personnel_id,
            "meeting_id": self.meeting_combo.currentData() or "",
            "gis_feature_id": self.gis_combo.currentData() or "",
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


_NO_CHANGE = "(no change)"
_CORRECTABLE_STATUSES = ("Scheduled", "In Progress", "Delayed", "Completed", "Cancelled")


class CorrectionDialog(QDialog):
    """An explicit, reason-logged override for reopening a terminal status
    or fixing an actual timestamp -- the one path allowed to bypass the
    routine transition table, per the Phase 1E /correct endpoint. Never
    used for routine status changes, which stay on the event-day actions.
    """

    def __init__(self, item: ScheduledItem, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Correct Activity")
        self.setMinimumWidth(380)
        self._item = item
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.status_combo = QComboBox()
        self.status_combo.addItem(_NO_CHANGE)
        self.status_combo.addItems(_CORRECTABLE_STATUSES)
        self.status_combo.setCurrentText(_NO_CHANGE)

        self.actual_start_edit = QDateTimeEdit()
        self.actual_start_edit.setCalendarPopup(True)
        self.actual_start_edit.setDisplayFormat("MM/dd/yyyy  HH:mm")
        self.actual_start_edit.setDateTime(to_qdatetime(item.actual_start_at or item.starts_at))
        self.actual_end_edit = QDateTimeEdit()
        self.actual_end_edit.setCalendarPopup(True)
        self.actual_end_edit.setDisplayFormat("MM/dd/yyyy  HH:mm")
        self.actual_end_edit.setDateTime(to_qdatetime(item.actual_end_at or item.ends_at))

        self.correct_actual_start_check = QComboBox()
        self.correct_actual_start_check.addItems([_NO_CHANGE, "Set actual start to:"])
        self.correct_actual_end_check = QComboBox()
        self.correct_actual_end_check.addItems([_NO_CHANGE, "Set actual end to:"])

        self.reason_edit = QTextEdit()
        self.reason_edit.setFixedHeight(60)
        self.reason_edit.setPlaceholderText("Required: why this activity's record is being corrected")

        form.addRow("Corrected status", self.status_combo)
        form.addRow("Actual start", self.correct_actual_start_check)
        form.addRow("", self.actual_start_edit)
        form.addRow("Actual end", self.correct_actual_end_check)
        form.addRow("", self.actual_end_edit)
        form.addRow("Reason", self.reason_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        if not self.reason_edit.toPlainText().strip():
            QMessageBox.warning(self, "Reason required", "Enter a reason for this correction.")
            return
        if (
            self.status_combo.currentText() == _NO_CHANGE
            and self.correct_actual_start_check.currentIndex() == 0
            and self.correct_actual_end_check.currentIndex() == 0
        ):
            QMessageBox.warning(self, "Nothing to correct", "Choose a status and/or an actual time to correct.")
            return
        self.accept()

    def values(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"reason": self.reason_edit.toPlainText().strip()}
        if self.status_combo.currentText() != _NO_CHANGE:
            payload["status"] = self.status_combo.currentText()
        if self.correct_actual_start_check.currentIndex() == 1:
            payload["actual_start_at"] = storage_dt(self.actual_start_edit)
        if self.correct_actual_end_check.currentIndex() == 1:
            payload["actual_end_at"] = storage_dt(self.actual_end_edit)
        return payload
