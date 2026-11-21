"""Event Schedule — Planned Events Toolkit (Phase 1A/1B + 1C).

`ScheduleWidget` is the top-level container opened from the menu: a
"Timeline" tab (Phase 1C's operational run-of-show,
`operational_timeline_widget.py`) and an "Activity List" tab (Phase 1A/1B's
sortable/filterable table, `ScheduleListWidget` below). Both tabs share one
`ScheduleController` so there is exactly one place that fetches schedule
items, applies mutations, and reacts to live updates — not two competing
scheduling systems.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .operational_timeline_widget import OperationalTimelineWidget
from .schedule_dialogs import ACTIVITY_TYPE_PRESETS, ScheduleItemDialog, prompt_cancellation_reason, prompt_delay_reason
from .schedule_time_utils import friendly_dt
from ..records import ScheduledItem
from ..schedule_controller import ScheduleController

STATUSES = ("Scheduled", "In Progress", "Completed", "Delayed", "Cancelled")
_ALL = "All"

_COLUMNS = (
    "Planned Start", "Activity", "Type", "Responsible", "Location",
    "Status", "Actual Start", "Actual End",
)


class ScheduleListWidget(QWidget):
    """Phase 1A/1B's sortable/filterable activity table."""

    def __init__(self, controller: ScheduleController, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self._build_ui()
        self.controller.itemsChanged.connect(self._populate)
        self.controller.statusMessage.connect(self._set_status)
        from utils.styles import subscribe_theme
        subscribe_theme(self, self._on_theme_changed)
        self._populate()

    def _on_theme_changed(self, _name: str) -> None:
        self._populate()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        title = QLabel("Activity List")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
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
        start_btn.clicked.connect(lambda: self._selected_item() and self.controller.start(self._selected_item().id))
        resume_btn.clicked.connect(lambda: self._selected_item() and self.controller.resume(self._selected_item().id))
        complete_btn.clicked.connect(lambda: self._selected_item() and self.controller.complete(self._selected_item().id))
        delay_btn.clicked.connect(self._delay_selected)
        cancel_btn.clicked.connect(self._cancel_selected)
        delete_btn.clicked.connect(self._delete_selected)
        refresh_btn.clicked.connect(self.controller.refresh)
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
        from utils.table_view_styles import apply_statusboard_table_behavior
        apply_statusboard_table_behavior(self.table, stretch_last_section=True)
        self.table.itemSelectionChanged.connect(self._update_action_buttons)
        layout.addWidget(self.table)
        self._update_action_buttons()

    def _set_status(self, message: str, is_error: bool) -> None:
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {'#b00020' if is_error else '#375a2b'};")

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

        return [item for item in self.controller.items() if matches(item)]

    def _populate(self, *_args: Any) -> None:
        from utils.styles import event_schedule_status_colors

        items = self._filtered_items()
        colors = event_schedule_status_colors()
        self.table.setRowCount(len(items))
        for row_idx, item in enumerate(items):
            values = [
                friendly_dt(item.starts_at),
                item.name,
                item.kind,
                item.assigned_to,
                item.location,
                item.status,
                friendly_dt(item.actual_start_at),
                friendly_dt(item.actual_end_at),
            ]
            badge = colors.get(item.status)
            for col_idx, value in enumerate(values):
                cell = QTableWidgetItem("" if value is None else str(value))
                if badge is not None:
                    cell.setBackground(badge["bg"])
                    cell.setForeground(badge["fg"])
                self.table.setItem(row_idx, col_idx, cell)
        self._update_action_buttons()

    def _new_item(self) -> None:
        if not self.controller.incident_id:
            self._set_status("Select an incident before creating activities.", True)
            return
        dialog = ScheduleItemDialog(incident_id=self.controller.incident_id, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.controller.create(**dialog.values())

    def _edit_selected(self) -> None:
        item = self._selected_item()
        if item is None or item.id is None:
            return
        dialog = ScheduleItemDialog(item, incident_id=self.controller.incident_id, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.controller.update(item.id, dialog.values())

    def _delete_selected(self) -> None:
        item = self._selected_item()
        if item is None or item.id is None:
            return
        if QMessageBox.question(
            self, "Delete Activity", f"Delete '{item.name}'?",
        ) != QMessageBox.StandardButton.Yes:
            return
        self.controller.delete(item.id)

    def _delay_selected(self) -> None:
        item = self._selected_item()
        if item is None or item.id is None:
            return
        reason = prompt_delay_reason(self)
        if reason is None:
            return
        self.controller.delay(item.id, delay_reason=reason)

    def _cancel_selected(self) -> None:
        item = self._selected_item()
        if item is None or item.id is None:
            return
        reason = prompt_cancellation_reason(self)
        if reason is None:
            return
        self.controller.cancel(item.id, cancellation_reason=reason)


class ScheduleWidget(QWidget):
    """Top-level Event Schedule panel: Timeline + Activity List tabs."""

    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        incident_id = None if incident_id is None else str(incident_id)
        layout = QVBoxLayout(self)
        title = QLabel("Event Schedule")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)

        # Parented to self so Qt destroys it (and drops its incident_cache
        # subscription) when this panel closes, instead of leaking a
        # controller that keeps refreshing forever after the panel is gone.
        self.controller = ScheduleController(incident_id, parent=self)
        tabs = QTabWidget()
        tabs.addTab(OperationalTimelineWidget(self.controller), "Timeline")
        tabs.addTab(ScheduleListWidget(self.controller), "Activity List")
        layout.addWidget(tabs)

    def refresh(self) -> None:
        self.controller.refresh()
