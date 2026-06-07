from __future__ import annotations

from typing import Any

from PySide6 import QtWidgets

class InstanceEditorPanel(QtWidgets.QWidget):
    def __init__(self, instance_service: Any | None = None, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.instance_service = instance_service
        self.header = QtWidgets.QLabel("No form loaded", self)
        self.form_area = QtWidgets.QScrollArea(self)
        self.form_body = QtWidgets.QWidget(self.form_area)
        self.form_layout = QtWidgets.QFormLayout(self.form_body)
        self.form_area.setWidget(self.form_body)
        self.form_area.setWidgetResizable(True)
        self.source_label = QtWidgets.QLabel("Auto-fill sources appear beside fields", self)
        self.override_reason = QtWidgets.QLineEdit(self)
        self.override_reason.setPlaceholderText("Override reason")
        self.save_button = QtWidgets.QPushButton("Save", self)
        self.refresh_button = QtWidgets.QPushButton("Refresh auto-filled fields", self)
        self.finalize_button = QtWidgets.QPushButton("Finalize", self)
        self.export_button = QtWidgets.QPushButton("Export PDF", self)
        buttons = QtWidgets.QHBoxLayout()
        for widget in (self.save_button, self.refresh_button, self.finalize_button, self.export_button):
            buttons.addWidget(widget)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.header)
        layout.addWidget(self.form_area)
        layout.addWidget(self.source_label)
        layout.addWidget(self.override_reason)
        layout.addLayout(buttons)

    def build_fields(self, fields: list[dict[str, Any]]) -> None:
        while self.form_layout.rowCount():
            self.form_layout.removeRow(0)
        for field in fields:
            editor = QtWidgets.QPlainTextEdit(self) if field.get("field_type") == "multiline_text" else QtWidgets.QLineEdit(self)
            editor.setProperty("field_key", field.get("key"))
            self.form_layout.addRow(field.get("label") or field.get("key", ""), editor)
