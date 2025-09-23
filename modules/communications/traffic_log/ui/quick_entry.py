"""Quick entry widget for rapid logging."""

from __future__ import annotations

from typing import Dict, Iterable, Optional

from PySide6.QtCore import Qt, QDateTime, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..models import (
    DIRECTION_INCOMING,
    DIRECTION_INTERNAL,
    DIRECTION_OUTGOING,
    PRIORITY_EMERGENCY,
    PRIORITY_PRIORITY,
    PRIORITY_ROUTINE,
)


class QuickEntryWidget(QWidget):
    """Bottom dock widget used for rapid keyboard-first data entry."""

    submitted = Signal(dict)
    attachmentsRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._attachments: list[str] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        layout.addLayout(top_row)

        self.timestamp_edit = QDateTimeEdit(QDateTime.currentDateTime())
        self.timestamp_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.timestamp_edit.setCalendarPopup(True)
        top_row.addWidget(QLabel("Timestamp"))
        top_row.addWidget(self.timestamp_edit)

        self.direction_combo = QComboBox()
        self.direction_combo.addItems([DIRECTION_INCOMING, DIRECTION_OUTGOING, DIRECTION_INTERNAL])
        top_row.addWidget(QLabel("Direction"))
        top_row.addWidget(self.direction_combo)

        self.priority_combo = QComboBox()
        self.priority_combo.addItems([PRIORITY_ROUTINE, PRIORITY_PRIORITY, PRIORITY_EMERGENCY])
        top_row.addWidget(QLabel("Priority"))
        top_row.addWidget(self.priority_combo)

        self.resource_combo = QComboBox()
        self.resource_combo.setEditable(True)
        top_row.addWidget(QLabel("Resource"))
        top_row.addWidget(self.resource_combo, 1)

        self.from_field = QLineEdit()
        self.from_field.setPlaceholderText("From unit/callsign")
        self.to_field = QLineEdit()
        self.to_field.setPlaceholderText("To unit/callsign")

        names_layout = QHBoxLayout()
        names_layout.addWidget(QLabel("From"))
        names_layout.addWidget(self.from_field)
        names_layout.addWidget(QLabel("To"))
        names_layout.addWidget(self.to_field)
        layout.addLayout(names_layout)

        message_layout = QHBoxLayout()
        self.message_edit = QTextEdit()
        self.message_edit.setPlaceholderText("Message body")
        self.message_edit.setTabChangesFocus(True)
        message_layout.addWidget(QLabel("Message"))
        message_layout.addWidget(self.message_edit, 1)
        layout.addLayout(message_layout)

        action_layout = QHBoxLayout()
        self.action_edit = QLineEdit()
        self.action_edit.setPlaceholderText("Action taken")
        action_layout.addWidget(QLabel("Action"))
        action_layout.addWidget(self.action_edit, 1)
        layout.addLayout(action_layout)

        toggle_layout = QHBoxLayout()
        self.status_checkbox = QCheckBox("Status Update")
        self.followup_checkbox = QCheckBox("Follow-up Required")
        toggle_layout.addWidget(self.status_checkbox)
        toggle_layout.addWidget(self.followup_checkbox)
        toggle_layout.addStretch(1)

        self.attach_button = QPushButton("Attach…")
        self.attach_button.clicked.connect(self.attachmentsRequested.emit)
        toggle_layout.addWidget(self.attach_button)

        self.save_button = QPushButton("Save")
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self._on_submit)
        toggle_layout.addWidget(self.save_button)

        layout.addLayout(toggle_layout)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_channels(self, channels: Iterable[Dict[str, str]]) -> None:
        self.resource_combo.clear()
        self.resource_combo.addItem("", None)
        for chan in channels:
            label = chan.get("display_name") or chan.get("name") or ""
            self.resource_combo.addItem(label, chan.get("id"))

    def set_default_resource(self, resource_id: Optional[int]) -> None:
        if resource_id is None:
            return
        for row in range(self.resource_combo.count()):
            if self.resource_combo.itemData(row) == resource_id:
                self.resource_combo.setCurrentIndex(row)
                break

    def reset(self) -> None:
        self.message_edit.clear()
        self.action_edit.clear()
        self.followup_checkbox.setChecked(False)
        self.status_checkbox.setChecked(False)
        self.from_field.clear()
        self.to_field.clear()
        self._attachments.clear()
        self.attach_button.setText("Attach…")
        self.message_edit.setFocus()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _on_submit(self) -> None:
        message = self.message_edit.toPlainText().strip()
        if not message:
            return
        ts_local = self.timestamp_edit.dateTime()
        payload = {
            "ts_local": ts_local.toString(Qt.ISODate),
            "ts_utc": ts_local.toUTC().toString(Qt.ISODate),
            "direction": self.direction_combo.currentText(),
            "priority": self.priority_combo.currentText(),
            "resource_label": self.resource_combo.currentText().strip(),
            "resource_id": self.resource_combo.currentData(),
            "from_unit": self.from_field.text().strip(),
            "to_unit": self.to_field.text().strip(),
            "message": message,
            "action_taken": self.action_edit.text().strip(),
            "follow_up_required": self.followup_checkbox.isChecked(),
            "is_status_update": self.status_checkbox.isChecked(),
            "attachments": list(self._attachments),
        }
        self.submitted.emit(payload)
        self.reset()

    # ------------------------------------------------------------------
    def add_attachments(self, paths: Iterable[str]) -> None:
        for path in paths:
            if path and path not in self._attachments:
                self._attachments.append(path)
        if self._attachments:
            self.attach_button.setText(f"Attach… ({len(self._attachments)})")


__all__ = ["QuickEntryWidget"]
