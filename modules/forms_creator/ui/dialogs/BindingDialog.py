"""Dialog for configuring field bindings."""
from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
)

from ...services.binder import Binder


class BindingDialog(QDialog):
    """Configure bindings for a single field."""

    def __init__(self, binder: Binder, current: list[dict[str, Any]] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configure Binding")
        self._binder = binder
        self._current = current or []
        self._result: list[dict[str, Any]] = self._current.copy()

        self._static_radio = QRadioButton("Static value")
        self._system_radio = QRadioButton("System data")
        self._static_value_edit = QLineEdit()
        self._system_combo = QComboBox()
        self._system_combo.addItems(self._binder.available_keys())
        self._context_edit = QTextEdit()
        self._context_edit.setPlaceholderText("Optional JSON context for testing bindings")
        test_button = QPushButton("Test Binding")
        test_button.clicked.connect(self._test_binding)
        self._preview_label = QLabel()
        self._preview_label.setWordWrap(True)

        form = QFormLayout()
        form.addRow(self._static_radio, self._static_value_edit)
        form.addRow(self._system_radio, self._system_combo)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel("Evaluation context (JSON)"))
        layout.addWidget(self._context_edit)
        layout.addWidget(test_button)
        layout.addWidget(self._preview_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if self._current:
            binding = self._current[0]
            if binding.get("source_type") == "system":
                self._system_radio.setChecked(True)
                index = max(0, self._system_combo.findText(binding.get("source_ref", "")))
                self._system_combo.setCurrentIndex(index)
            else:
                self._static_radio.setChecked(True)
                self._static_value_edit.setText(binding.get("source_ref", ""))
        else:
            self._static_radio.setChecked(True)

    # ------------------------------------------------------------------
    @property
    def bindings(self) -> list[dict[str, Any]]:
        return self._result

    # ------------------------------------------------------------------
    def accept(self) -> None:  # noqa: N802
        if self._static_radio.isChecked():
            value = self._static_value_edit.text()
            self._result = [
                {
                    "source_type": "static",
                    "source_ref": value,
                }
            ]
        else:
            system_key = self._system_combo.currentText()
            if not system_key:
                QMessageBox.warning(self, "Select key", "Please choose a system key to bind to.")
                return
            self._result = [
                {
                    "source_type": "system",
                    "source_ref": system_key,
                }
            ]
        super().accept()

    def _test_binding(self) -> None:
        context_text = self._context_edit.toPlainText().strip()
        context: dict[str, Any] = {}
        if context_text:
            try:
                context = json.loads(context_text)
            except json.JSONDecodeError as exc:
                QMessageBox.warning(self, "Invalid JSON", f"Unable to parse context: {exc}")
                return
        if self._static_radio.isChecked():
            value = self._static_value_edit.text()
        else:
            key = self._system_combo.currentText()
            value = self._binder.resolve(context, key)
        self._preview_label.setText(f"Preview value: <b>{value}</b>")

