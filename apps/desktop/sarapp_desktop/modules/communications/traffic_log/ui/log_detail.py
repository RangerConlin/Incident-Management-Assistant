"""Detail drawer widget for reviewing and editing an entry."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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


def _lbl(text: str) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet("font-size: 10px; color: #90a4ae; font-weight: 600;")
    return l


class LogDetailDrawer(QWidget):
    """Compact detail panel for reviewing and editing a selected log entry."""

    saveRequested = Signal(int, dict)
    createTaskRequested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entry: Optional[CommsLogEntry] = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        root.setSpacing(4)

        # ── Header ────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        self.header_label = QLabel("Select a log entry to view details")
        self.header_label.setStyleSheet("font-size: 11px; font-weight: 700;")
        hdr.addWidget(self.header_label, 1)
        self.save_button = QPushButton("Save")
        self.save_button.setFixedHeight(24)
        self.save_button.setFixedWidth(54)
        self.save_button.clicked.connect(self._on_save)
        hdr.addWidget(self.save_button)
        self.task_button = QPushButton("+ Task")
        self.task_button.setFixedHeight(24)
        self.task_button.setFixedWidth(54)
        self.task_button.clicked.connect(self._on_create_task)
        hdr.addWidget(self.task_button)
        root.addLayout(hdr)

        # ── Two-column grid: meta fields ──────────────────────────────────
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(2)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        grid.addWidget(_lbl("Timestamp"), 0, 0)
        self.ts_label = QLabel("—")
        self.ts_label.setStyleSheet("font-size: 11px;")
        grid.addWidget(self.ts_label, 0, 1, 1, 3)

        grid.addWidget(_lbl("Priority"), 1, 0)
        self.priority_combo = QComboBox()
        self.priority_combo.addItems([PRIORITY_ROUTINE, PRIORITY_PRIORITY, PRIORITY_EMERGENCY])
        self.priority_combo.setFixedHeight(22)
        grid.addWidget(self.priority_combo, 1, 1)

        grid.addWidget(_lbl("Disposition"), 1, 2)
        self.disposition_combo = QComboBox()
        self.disposition_combo.addItems([DISPOSITION_OPEN, DISPOSITION_CLOSED])
        self.disposition_combo.setFixedHeight(22)
        grid.addWidget(self.disposition_combo, 1, 3)

        grid.addWidget(_lbl("Channel"), 2, 0)
        self.channel_field = QLineEdit()
        self.channel_field.setReadOnly(True)
        self.channel_field.setFixedHeight(22)
        grid.addWidget(self.channel_field, 2, 1)

        grid.addWidget(_lbl("Attachments"), 2, 2)
        self.attachment_label = QLabel("—")
        self.attachment_label.setStyleSheet("font-size: 11px;")
        grid.addWidget(self.attachment_label, 2, 3)

        grid.addWidget(_lbl("From"), 3, 0)
        self.from_field = QLineEdit()
        self.from_field.setFixedHeight(22)
        grid.addWidget(self.from_field, 3, 1)

        grid.addWidget(_lbl("To"), 3, 2)
        self.to_field = QLineEdit()
        self.to_field.setFixedHeight(22)
        grid.addWidget(self.to_field, 3, 3)

        root.addLayout(grid)

        # ── Message ───────────────────────────────────────────────────────
        root.addWidget(_lbl("Message"))
        self.message_edit = QTextEdit()
        self.message_edit.setPlaceholderText("Message content")
        self.message_edit.setFixedHeight(56)
        root.addWidget(self.message_edit)

        # ── Flags row ─────────────────────────────────────────────────────
        flags = QHBoxLayout()
        self.follow_checkbox = QCheckBox("Follow-up Required")
        self.follow_checkbox.setStyleSheet("font-size: 11px;")
        flags.addWidget(self.follow_checkbox)
        self.status_checkbox = QCheckBox("Status Update")
        self.status_checkbox.setStyleSheet("font-size: 11px;")
        flags.addWidget(self.status_checkbox)
        flags.addStretch()
        root.addLayout(flags)

        # ── Diff hint ─────────────────────────────────────────────────────
        self.diff_label = QLabel("")
        self.diff_label.setWordWrap(True)
        self.diff_label.setStyleSheet("color: #78909c; font-size: 10px;")
        root.addWidget(self.diff_label)

        # Wire change signals
        self.from_field.textChanged.connect(self._update_diff)
        self.to_field.textChanged.connect(self._update_diff)
        self.message_edit.textChanged.connect(self._update_diff)
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
            self.disposition_combo.setCurrentIndex(0)
            self.follow_checkbox.setChecked(False)
            self.status_checkbox.setChecked(False)
            self.attachment_label.setText("—")
            self.diff_label.clear()
            self.setEnabled(False)
            return

        self.setEnabled(True)
        self.header_label.setText(f"Entry #{entry.id}")
        self.ts_label.setText(f"{entry.ts_local}  /  {entry.ts_utc} UTC")
        self.priority_combo.setCurrentText(entry.priority)
        self.channel_field.setText(entry.resource_label)
        self.from_field.setText(entry.from_unit)
        self.to_field.setText(entry.to_unit)
        self.message_edit.setPlainText(entry.message)
        self.disposition_combo.setCurrentText(entry.disposition)
        self.follow_checkbox.setChecked(entry.follow_up_required)
        self.status_checkbox.setChecked(entry.is_status_update)
        count = len(entry.attachments)
        self.attachment_label.setText(str(count) if count else "—")
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
        if entry.disposition != self.disposition_combo.currentText():
            patch["disposition"] = self.disposition_combo.currentText()
        if entry.follow_up_required != self.follow_checkbox.isChecked():
            patch["follow_up_required"] = self.follow_checkbox.isChecked()
        if entry.is_status_update != self.status_checkbox.isChecked():
            patch["is_status_update"] = self.status_checkbox.isChecked()
        return patch

    def pending_patch(self) -> dict:
        return self._collect_patch()

    def _update_diff(self) -> None:
        patch = self._collect_patch()
        if not patch:
            self.diff_label.setText("")
            return
        keys = ", ".join(patch.keys())
        self.diff_label.setText(f"Unsaved changes: {keys}")

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
