"""Event Schedule — Planned Events Toolkit (Phase 1A/1B).

An operational run-of-show: activities shown chronologically with planned
vs. actual timing, responsibility, location, and status, plus the five
event-day actions (Start/Complete/Delay/Resume/Cancel) that drive the
status machine the backend enforces (see plannedtoolkit.py).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .. import services
from ..records import ScheduledItem
from utils.api_client import APIError
from utils.styles import event_schedule_status_colors, subscribe_theme
from utils.table_view_styles import apply_statusboard_table_behavior

STATUSES = ("Scheduled", "In Progress", "Completed", "Delayed", "Cancelled")
ACTIVITY_TYPE_PRESETS = (
    "Milestone", "Briefing", "Opening", "Closure", "Shift Change",
    "Inspection", "Performance", "Announcement", "Demobilization", "Other",
)
_ALL = "All"

_COLUMNS = (
    "Planned Start", "Activity", "Type", "Responsible", "Location",
    "Status", "Actual Start", "Actual End",
)


def _parse_dt(value: str) -> datetime | None:
    if not value:
        return None
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        try:
            return datetime.fromisoformat(text.replace(" ", "T"))
        except ValueError:
            return None


def _friendly_dt(value: str) -> str:
    dt = _parse_dt(value)
    if dt is None:
        return ""
    return dt.strftime("%b %d  %H:%M")


def _to_qdatetime(value: str) -> QDateTime:
    dt = _parse_dt(value)
    if dt is None:
        return QDateTime.currentDateTime()
    return QDateTime(dt.year, dt.month, dt.day, dt.hour, dt.minute)


def _storage_dt(editor: QDateTimeEdit) -> str:
    return editor.dateTime().toString(Qt.ISODate)


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

        self.starts_edit = QDateTimeEdit(QDateTime.currentDateTime())
        self.starts_edit.setCalendarPopup(True)
        self.starts_edit.setDisplayFormat("MM/dd/yyyy  HH:mm")
        self.ends_edit = QDateTimeEdit(QDateTime.currentDateTime().addSecs(1800))
        self.ends_edit.setCalendarPopup(True)
        self.ends_edit.setDisplayFormat("MM/dd/yyyy  HH:mm")

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
            self.starts_edit.setDateTime(_to_qdatetime(item.starts_at))
        if item.ends_at:
            self.ends_edit.setDateTime(_to_qdatetime(item.ends_at))
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
            "starts_at": _storage_dt(self.starts_edit),
            "ends_at": _storage_dt(self.ends_edit),
            "time_zone": self.time_zone_edit.text().strip(),
            "location": self.location_edit.text().strip(),
            "assigned_to": self.assigned_to_edit.text().strip(),
            "assigned_team_id": self.assigned_team_id_edit.text().strip(),
            "assigned_person_id": self.assigned_person_id_edit.text().strip(),
            "meeting_id": self.meeting_id_edit.text().strip(),
            "notes": self.notes_edit.toPlainText().strip(),
        }


class ScheduleWidget(QWidget):
    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.incident_id = None if incident_id is None else str(incident_id)
        self._items: list[ScheduledItem] = []
        self._build_ui()
        subscribe_theme(self, self._on_theme_changed)
        self.refresh()

    def _on_theme_changed(self, _name: str) -> None:
        self._populate()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        title = QLabel("Event Schedule")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.status_label)
        layout.addLayout(header)

        filters = QHBoxLayout()
        self.date_filter_edit = QLineEdit()
        self.date_filter_edit.setPlaceholderText("Filter by date (YYYY-MM-DD)")
        self.status_filter_combo = QComboBox()
        self.status_filter_combo.addItems([_ALL, *STATUSES])
        self.type_filter_combo = QComboBox()
        self.type_filter_combo.addItems([_ALL, *ACTIVITY_TYPE_PRESETS])
        self.type_filter_combo.setEditable(True)
        self.responsible_filter_edit = QLineEdit()
        self.responsible_filter_edit.setPlaceholderText("Filter by responsible person/team")
        for widget in (
            self.date_filter_edit, self.status_filter_combo,
            self.type_filter_combo, self.responsible_filter_edit,
        ):
            filters.addWidget(widget)
        self.date_filter_edit.textChanged.connect(self._populate)
        self.status_filter_combo.currentTextChanged.connect(self._populate)
        self.type_filter_combo.currentTextChanged.connect(self._populate)
        self.responsible_filter_edit.textChanged.connect(self._populate)
        layout.addLayout(filters)

        actions = QHBoxLayout()
        new_btn = QPushButton("New Activity")
        edit_btn = QPushButton("Edit")
        start_btn = QPushButton("Start Activity")
        resume_btn = QPushButton("Resume Activity")
        complete_btn = QPushButton("Complete Activity")
        delay_btn = QPushButton("Mark Delayed")
        cancel_btn = QPushButton("Cancel Activity")
        delete_btn = QPushButton("Delete")
        refresh_btn = QPushButton("Refresh")
        new_btn.clicked.connect(self._new_item)
        edit_btn.clicked.connect(self._edit_selected)
        start_btn.clicked.connect(self._start_selected)
        resume_btn.clicked.connect(self._resume_selected)
        complete_btn.clicked.connect(self._complete_selected)
        delay_btn.clicked.connect(self._delay_selected)
        cancel_btn.clicked.connect(self._cancel_selected)
        delete_btn.clicked.connect(self._delete_selected)
        refresh_btn.clicked.connect(self.refresh)
        self._action_buttons = {
            "start": start_btn, "resume": resume_btn, "complete": complete_btn,
            "delay": delay_btn, "cancel": cancel_btn, "edit": edit_btn, "delete": delete_btn,
        }
        for button in (new_btn, edit_btn, start_btn, resume_btn, complete_btn, delay_btn, cancel_btn, delete_btn, refresh_btn):
            actions.addWidget(button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(list(_COLUMNS))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        apply_statusboard_table_behavior(self.table, stretch_last_section=True)
        self.table.itemSelectionChanged.connect(self._update_action_buttons)
        layout.addWidget(self.table)
        self._update_action_buttons()

    # -- data -----------------------------------------------------------

    def _iid(self) -> str | None:
        return self.incident_id

    def _set_status(self, message: str, *, error: bool = False) -> None:
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {'#b00020' if error else '#375a2b'};")

    def _describe_error(self, exc: Exception) -> str:
        if isinstance(exc, APIError):
            if exc.status_code is None:
                return f"Schedule API unavailable: {exc}"
            return f"Schedule API error {exc.status_code}: {exc}"
        return str(exc)

    def refresh(self) -> None:
        if not self._iid():
            self._items = []
            self._populate()
            self._set_status("Select an incident to use the Event Schedule.", error=True)
            return
        try:
            rows = services.list_schedule_items(self._iid())
        except Exception as exc:
            self._items = []
            self._populate()
            self._set_status(self._describe_error(exc), error=True)
            return
        self._items = sorted(rows, key=lambda row: row.starts_at or "")
        self._populate()
        self._set_status(f"{len(self._items)} activities")

    # -- selection --------------------------------------------------------

    def _selected_item(self) -> ScheduledItem | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        items = self._filtered_items()
        if row >= len(items):
            return None
        return items[row]

    def _update_action_buttons(self) -> None:
        item = self._selected_item()
        enabled = {key: False for key in self._action_buttons}
        if item is not None:
            enabled["edit"] = item.status not in ("Completed", "Cancelled")
            enabled["delete"] = True
            enabled["start"] = item.status == "Scheduled"
            enabled["resume"] = item.status == "Delayed"
            enabled["complete"] = item.status in ("In Progress", "Delayed")
            enabled["delay"] = item.status in ("Scheduled", "In Progress")
            enabled["cancel"] = item.status in ("Scheduled", "In Progress", "Delayed")
        for key, button in self._action_buttons.items():
            button.setEnabled(enabled[key])

    # -- filtering --------------------------------------------------------

    def _filtered_items(self) -> list[ScheduledItem]:
        date_text = self.date_filter_edit.text().strip()
        status_text = self.status_filter_combo.currentText()
        type_text = self.type_filter_combo.currentText().strip()
        responsible_text = self.responsible_filter_edit.text().strip().lower()

        def matches(item: ScheduledItem) -> bool:
            if date_text and not item.starts_at.startswith(date_text):
                return False
            if status_text != _ALL and item.status != status_text:
                return False
            if type_text and type_text != _ALL and item.kind != type_text:
                return False
            if responsible_text and responsible_text not in item.assigned_to.lower():
                return False
            return True

        return [item for item in self._items if matches(item)]

    # -- rendering --------------------------------------------------------

    def _populate(self, *_args: Any) -> None:
        items = self._filtered_items()
        colors = event_schedule_status_colors()
        self.table.setRowCount(len(items))
        for row_idx, item in enumerate(items):
            values = [
                _friendly_dt(item.starts_at),
                item.name,
                item.kind,
                item.assigned_to,
                item.location,
                item.status,
                _friendly_dt(item.actual_start_at),
                _friendly_dt(item.actual_end_at),
            ]
            badge = colors.get(item.status)
            for col_idx, value in enumerate(values):
                cell = QTableWidgetItem("" if value is None else str(value))
                if badge is not None:
                    cell.setBackground(badge["bg"])
                    cell.setForeground(badge["fg"])
                self.table.setItem(row_idx, col_idx, cell)

    # -- actions ------------------------------------------------------------

    def _new_item(self) -> None:
        if not self._iid():
            self._set_status("Select an incident before creating activities.", error=True)
            return
        dialog = ScheduleItemDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            services.create_schedule_item(self._iid(), **dialog.values())
        except Exception as exc:
            self._set_status(self._describe_error(exc), error=True)
            return
        self.refresh()

    def _edit_selected(self) -> None:
        item = self._selected_item()
        if item is None or item.id is None:
            return
        dialog = ScheduleItemDialog(item, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            services.update_schedule_item(item.id, dialog.values(), self._iid())
        except Exception as exc:
            self._set_status(self._describe_error(exc), error=True)
            return
        self.refresh()

    def _delete_selected(self) -> None:
        item = self._selected_item()
        if item is None or item.id is None:
            return
        if QMessageBox.question(
            self, "Delete Activity", f"Delete '{item.name}'?",
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            services.delete_schedule_item(item.id, self._iid())
        except Exception as exc:
            self._set_status(self._describe_error(exc), error=True)
            return
        self.refresh()

    def _start_selected(self) -> None:
        item = self._selected_item()
        if item is None or item.id is None:
            return
        try:
            services.start_schedule_item(item.id, self._iid())
        except Exception as exc:
            self._set_status(self._describe_error(exc), error=True)
            return
        self.refresh()

    def _resume_selected(self) -> None:
        item = self._selected_item()
        if item is None or item.id is None:
            return
        try:
            services.resume_schedule_item(item.id, self._iid())
        except Exception as exc:
            self._set_status(self._describe_error(exc), error=True)
            return
        self.refresh()

    def _complete_selected(self) -> None:
        item = self._selected_item()
        if item is None or item.id is None:
            return
        try:
            services.complete_schedule_item(item.id, self._iid())
        except Exception as exc:
            self._set_status(self._describe_error(exc), error=True)
            return
        self.refresh()

    def _delay_selected(self) -> None:
        item = self._selected_item()
        if item is None or item.id is None:
            return
        reason, ok = QInputDialog.getMultiLineText(self, "Mark Delayed", "Delay reason (required):")
        if not ok or not reason.strip():
            return
        try:
            services.delay_schedule_item(item.id, self._iid(), delay_reason=reason.strip())
        except Exception as exc:
            self._set_status(self._describe_error(exc), error=True)
            return
        self.refresh()

    def _cancel_selected(self) -> None:
        item = self._selected_item()
        if item is None or item.id is None:
            return
        reason, ok = QInputDialog.getMultiLineText(self, "Cancel Activity", "Cancellation reason (required):")
        if not ok or not reason.strip():
            return
        try:
            services.cancel_schedule_item(item.id, self._iid(), cancellation_reason=reason.strip())
        except Exception as exc:
            self._set_status(self._describe_error(exc), error=True)
            return
        self.refresh()
