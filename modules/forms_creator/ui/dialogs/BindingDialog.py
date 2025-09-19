"""Dialog used to configure field bindings."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)

from ...services.binder import Binder


class BindingDialog(QDialog):
    """Simple binding editor supporting static and system bindings."""

    def __init__(self, config: dict[str, Any], binder: Binder, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Field Bindings")
        self.binder = binder
        self.bindings: list[dict[str, Any]] = config.get("bindings", []).copy()

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.type_combo = QComboBox()
        self.type_combo.addItem("Static", "static")
        self.type_combo.addItem("System", "system")
        form.addRow("Source Type", self.type_combo)

        self.static_edit = QLineEdit()
        form.addRow("Static Value", self.static_edit)

        self.system_combo = QComboBox()
        self.system_bindings = binder.available_keys()
        for binding in self.system_bindings:
            self.system_combo.addItem(binding.label, binding.key)
            if binding.description:
                self.system_combo.setItemData(
                    self.system_combo.count() - 1,
                    binding.description,
                    Qt.ItemDataRole.ToolTipRole,
                )
        form.addRow("System Key", self.system_combo)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(button_box)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        self.type_combo.currentIndexChanged.connect(self._sync_controls)
        self._load_initial_state()

    def _load_initial_state(self) -> None:
        if not self.bindings:
            self._sync_controls()
            return
        binding = self.bindings[0]
        source_type = binding.get("source_type", "static")
        index = self.type_combo.findData(source_type)
        if index >= 0:
            self.type_combo.setCurrentIndex(index)
        if source_type == "static":
            self.static_edit.setText(binding.get("value", ""))
        elif source_type == "system":
            key = binding.get("source_ref", "")
            idx = self.system_combo.findData(key)
            if idx >= 0:
                self.system_combo.setCurrentIndex(idx)
        self._sync_controls()

    def _sync_controls(self) -> None:
        source_type = self.type_combo.currentData()
        self.static_edit.setEnabled(source_type == "static")
        self.system_combo.setEnabled(source_type == "system")

    def accept(self) -> None:  # noqa: D401
        source_type = self.type_combo.currentData()
        if source_type == "static":
            binding = {"source_type": "static", "value": self.static_edit.text()}
        else:
            binding = {"source_type": "system", "source_ref": self.system_combo.currentData()}
        self.bindings = [binding]
        super().accept()
