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
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ...services.binder import Binder


class CustomBindingDialog(QDialog):
    """Collect information for a custom system binding entry."""

    def __init__(self, reserved_keys: set[str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Custom Binding")
        self.setWhatsThis(
            "Define a new dotted key that will appear alongside the built-in bindings."
        )
        self._reserved_keys = reserved_keys
        self._result: dict[str, str | None] | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("Display name shown in menus (e.g. Operations Chief)")
        self.label_edit.setToolTip("Human-friendly label that appears in binding pickers.")
        form.addRow("Label", self.label_edit)

        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("incident.teams.current.leader_name")
        self.key_edit.setToolTip(
            "Unique dotted path looked up when a form instance is generated."
        )
        form.addRow("Key", self.key_edit)

        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText("Optional helper text for other authors")
        self.description_edit.setToolTip(
            "Optional note shown as a tooltip when selecting the binding."
        )
        form.addRow("Description", self.description_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------
    def _on_accept(self) -> None:
        label = self.label_edit.text().strip()
        key = self.key_edit.text().strip()
        description = self.description_edit.text().strip()

        if not label or not key:
            QMessageBox.warning(self, "Custom Binding", "Both label and key are required.")
            return

        if key in self._reserved_keys:
            QMessageBox.warning(
                self,
                "Custom Binding",
                "The specified key matches a built-in binding and cannot be overridden.",
            )
            return

        self._result = {
            "label": label,
            "key": key,
            "description": description or None,
        }
        self.accept()

    # ------------------------------------------------------------------
    def data(self) -> dict[str, str | None] | None:
        """Return the collected binding metadata."""

        return self._result


class BindingDialog(QDialog):
    """Simple binding editor supporting static and system bindings."""

    def __init__(self, config: dict[str, Any], binder: Binder, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Field Bindings")
        self.setWhatsThis(
            "Assign either a fixed value or an incident data key to the selected field."
        )
        self.binder = binder
        self.bindings: list[dict[str, Any]] = config.get("bindings", []).copy()

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.type_combo = QComboBox()
        self.type_combo.addItem("Static", "static")
        self.type_combo.addItem("System", "system")
        self.type_combo.setToolTip(
            "Choose whether the field should use a fixed value or pull from incident data."
        )
        form.addRow("Source Type", self.type_combo)

        self.static_edit = QLineEdit()
        self.static_edit.setPlaceholderText("Text inserted every time this form is generated")
        self.static_edit.setToolTip("Enter the literal value to pre-fill this field with.")
        form.addRow("Static Value", self.static_edit)

        self.system_combo = QComboBox()
        self._reload_system_bindings()
        self.system_combo.setToolTip(
            "Select which incident data point should populate this field."
        )
        form.addRow("System Key", self.system_combo)

        self.add_custom_button = QPushButton("Add Custom Binding…")
        self.add_custom_button.clicked.connect(self._add_custom_binding)
        self.add_custom_button.setToolTip(
            "Create a reusable key that maps to your own data source or workflow."
        )
        layout.addWidget(self.add_custom_button)

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
        self.add_custom_button.setEnabled(source_type == "system")

    def accept(self) -> None:  # noqa: D401
        source_type = self.type_combo.currentData()
        if source_type == "static":
            binding = {"source_type": "static", "value": self.static_edit.text()}
        else:
            binding = {"source_type": "system", "source_ref": self.system_combo.currentData()}
        self.bindings = [binding]
        super().accept()

    # ------------------------------------------------------------------
    def _reload_system_bindings(self, *, select_key: str | None = None) -> None:
        self.system_combo.clear()
        self.system_bindings = self.binder.available_keys()
        for binding in self.system_bindings:
            self.system_combo.addItem(binding.label, binding.key)
            if binding.description:
                self.system_combo.setItemData(
                    self.system_combo.count() - 1,
                    binding.description,
                    Qt.ItemDataRole.ToolTipRole,
                )
        if select_key:
            idx = self.system_combo.findData(select_key)
            if idx >= 0:
                self.system_combo.setCurrentIndex(idx)

    def _add_custom_binding(self) -> None:
        dialog = CustomBindingDialog(self.binder.built_in_keys(), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.data()
        if not data:
            return
        try:
            binding = self.binder.add_custom_binding(
                key=str(data["key"]),
                label=str(data["label"]),
                description=data.get("description"),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Custom Binding", str(exc))
            return
        self._reload_system_bindings(select_key=binding.key)
