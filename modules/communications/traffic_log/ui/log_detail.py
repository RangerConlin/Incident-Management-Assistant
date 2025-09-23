"""Detail drawer widget for reviewing and editing an entry."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..models import (
    CommsLogEntry,
    DISPOSITION_CLOSED,
    DISPOSITION_OPEN,
    PRIORITY_EMERGENCY,
    PRIORITY_PRIORITY,
    PRIORITY_ROUTINE,
)


class LogDetailDrawer(QWidget):
    """Slide-in widget presenting the full entry view."""

    saveRequested = Signal(int, dict)
    createTaskRequested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entry: Optional[CommsLogEntry] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        self.header_label = QLabel("Select a log entry to view details")
        self.header_label.setWordWrap(True)
        layout.addWidget(self.header_label)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)

        self.ts_label = QLabel("—")
        form.addRow("Timestamp", self.ts_label)

        self.priority_combo = QComboBox()
        self.priority_combo.addItems([PRIORITY_ROUTINE, PRIORITY_PRIORITY, PRIORITY_EMERGENCY])
        form.addRow("Priority", self.priority_combo)

        self.channel_field = QLineEdit()
        self.channel_field.setReadOnly(True)
        form.addRow("Channel", self.channel_field)

        self.from_field = QLineEdit()
        self.to_field = QLineEdit()
        form.addRow("From", self.from_field)
        form.addRow("To", self.to_field)

        self.message_edit = QTextEdit()
        self.message_edit.setPlaceholderText("Message content")
        form.addRow("Message", self.message_edit)

        self.action_edit = QTextEdit()
        self.action_edit.setPlaceholderText("Action taken")
        form.addRow("Action", self.action_edit)

        self.disposition_combo = QComboBox()
        self.disposition_combo.addItems([DISPOSITION_OPEN, DISPOSITION_CLOSED])
        form.addRow("Disposition", self.disposition_combo)

        self.follow_checkbox = QCheckBox("Follow-up Required")
        form.addRow("Follow-up", self.follow_checkbox)

        self.status_checkbox = QCheckBox("Status Update")
        form.addRow("Status", self.status_checkbox)

        self.notification_field = QLineEdit()
        form.addRow("Notification", self.notification_field)

        self.related_label = QLabel("—")
        self.related_label.setWordWrap(True)
        form.addRow("Related", self.related_label)

        layout.addLayout(form)

        layout.addWidget(QLabel("Attachments"))
        self.attachment_list = QListWidget()
        layout.addWidget(self.attachment_list)

        self.diff_label = QLabel("")
        self.diff_label.setWordWrap(True)
        self.diff_label.setStyleSheet("color: #5A5F6A; font-size: 11px;")
        layout.addWidget(self.diff_label)

        button_row = QHBoxLayout()
        self.save_button = QPushButton("Save Changes")
        self.save_button.clicked.connect(self._on_save)
        button_row.addWidget(self.save_button)

        self.task_button = QPushButton("Create Task")
        self.task_button.clicked.connect(self._on_create_task)
        button_row.addWidget(self.task_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        # Track edits to update diff preview
        self.from_field.textChanged.connect(self._update_diff)
        self.to_field.textChanged.connect(self._update_diff)
        self.message_edit.textChanged.connect(self._update_diff)
        self.action_edit.textChanged.connect(self._update_diff)
        self.notification_field.textChanged.connect(self._update_diff)
        self.follow_checkbox.toggled.connect(self._update_diff)
        self.status_checkbox.toggled.connect(self._update_diff)
        self.priority_combo.currentIndexChanged.connect(self._update_diff)
        self.disposition_combo.currentIndexChanged.connect(self._update_diff)

    # ------------------------------------------------------------------
    def display_entry(self, entry: Optional[CommsLogEntry]) -> None:
        self._entry = entry
        if not entry:
            self.header_label.setText("Select a log entry to view details")
            self.ts_label.setText("—")
            self.channel_field.setText("")
            self.from_field.setText("")
            self.to_field.setText("")
            self.message_edit.clear()
            self.action_edit.clear()
            self.disposition_combo.setCurrentIndex(0)
            self.follow_checkbox.setChecked(False)
            self.status_checkbox.setChecked(False)
            self.notification_field.clear()
            self.attachment_list.clear()
            self.related_label.setText("—")
            self.diff_label.clear()
            self.setEnabled(False)
            return

        self.setEnabled(True)
        self.header_label.setText(f"Entry #{entry.id} — {entry.ts_local}")
        self.ts_label.setText(f"Local: {entry.ts_local}\nUTC: {entry.ts_utc}")
        self.priority_combo.setCurrentText(entry.priority)
        self.channel_field.setText(entry.resource_label)
        self.from_field.setText(entry.from_unit)
        self.to_field.setText(entry.to_unit)
        self.message_edit.setPlainText(entry.message)
        self.action_edit.setPlainText(entry.action_taken)
        self.disposition_combo.setCurrentText(entry.disposition)
        self.follow_checkbox.setChecked(entry.follow_up_required)
        self.status_checkbox.setChecked(entry.is_status_update)
        self.notification_field.setText(entry.notification_level or "")
        related_bits = []
        if entry.task_id:
            related_bits.append(f"Task {entry.task_id}")
        if entry.team_id:
            related_bits.append(f"Team {entry.team_id}")
        if entry.vehicle_id:
            related_bits.append(f"Vehicle {entry.vehicle_id}")
        if entry.personnel_id:
            related_bits.append(f"Personnel {entry.personnel_id}")
        self.related_label.setText(", ".join(related_bits) if related_bits else "—")
        self.attachment_list.clear()
        for item in entry.attachments:
            self.attachment_list.addItem(QListWidgetItem(item))
        self._update_diff()

    def _collect_patch(self) -> dict:
        if not self._entry:
            return {}
        entry = self._entry
        patch = {}
        if entry.priority != self.priority_combo.currentText():
            patch["priority"] = self.priority_combo.currentText()
        if entry.from_unit != self.from_field.text():
            patch["from_unit"] = self.from_field.text()
        if entry.to_unit != self.to_field.text():
            patch["to_unit"] = self.to_field.text()
        if entry.message != self.message_edit.toPlainText():
            patch["message"] = self.message_edit.toPlainText()
        if entry.action_taken != self.action_edit.toPlainText():
            patch["action_taken"] = self.action_edit.toPlainText()
        if entry.disposition != self.disposition_combo.currentText():
            patch["disposition"] = self.disposition_combo.currentText()
        if entry.follow_up_required != self.follow_checkbox.isChecked():
            patch["follow_up_required"] = self.follow_checkbox.isChecked()
        if entry.is_status_update != self.status_checkbox.isChecked():
            patch["is_status_update"] = self.status_checkbox.isChecked()
        if (entry.notification_level or "") != self.notification_field.text():
            patch["notification_level"] = self.notification_field.text()
        attachments = [self.attachment_list.item(i).text() for i in range(self.attachment_list.count())]
        if attachments != entry.attachments:
            patch["attachments"] = attachments
        return patch

    def pending_patch(self) -> dict:
        """Return the current unsaved modifications."""
        return self._collect_patch()

    def _update_diff(self) -> None:
        patch = self._collect_patch()
        if not patch:
            self.diff_label.setText("")
            return
        parts = [f"{key} → {value}" for key, value in patch.items()]
        self.diff_label.setText("Pending changes: " + "; ".join(parts))

    def _on_save(self) -> None:
        if not self._entry:
            return
        patch = self._collect_patch()
        if not patch:
            return
        self.saveRequested.emit(int(self._entry.id), patch)

    def _on_create_task(self) -> None:
        if not self._entry:
            return
        self.createTaskRequested.emit(int(self._entry.id))


__all__ = ["LogDetailDrawer"]
