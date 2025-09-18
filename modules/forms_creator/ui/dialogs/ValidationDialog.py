"""Dialog for configuring field validation rules."""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)


class ValidationDialog(QDialog):
    """Allow the author to define validation rules for a field."""

    def __init__(self, current: list[dict[str, Any]] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Field Validation")
        self._current = current or []
        self._result: list[dict[str, Any]] = self._current.copy()

        self._required_checkbox = QCheckBox("Required")
        self._regex_edit = QLineEdit()
        self._regex_edit.setPlaceholderText("Regular expression")
        self._min_spin = QSpinBox()
        self._max_spin = QSpinBox()
        self._min_spin.setRange(-999999, 999999)
        self._max_spin.setRange(-999999, 999999)
        self._allowed_values_edit = QLineEdit()
        self._allowed_values_edit.setPlaceholderText("Comma separated values")

        form = QFormLayout()
        form.addRow("Required", self._required_checkbox)
        form.addRow("Regex", self._regex_edit)
        numeric_row = QHBoxLayout()
        numeric_row.addWidget(self._min_spin)
        numeric_row.addWidget(self._max_spin)
        form.addRow("Range (min / max)", numeric_row)
        form.addRow("Allowed values", self._allowed_values_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self._load_current()

    # ------------------------------------------------------------------
    @property
    def rules(self) -> list[dict[str, Any]]:
        return self._result

    # ------------------------------------------------------------------
    def accept(self) -> None:  # noqa: N802
        rules: list[dict[str, Any]] = []
        if self._required_checkbox.isChecked():
            rules.append({"rule_type": "required", "rule_config": None, "error_message": "This field is required."})
        if self._regex_edit.text().strip():
            rules.append(
                {
                    "rule_type": "regex",
                    "rule_config": {"pattern": self._regex_edit.text().strip()},
                    "error_message": "Invalid format.",
                }
            )
        if self._min_spin.value() or self._max_spin.value():
            rules.append(
                {
                    "rule_type": "range",
                    "rule_config": {"min": self._min_spin.value(), "max": self._max_spin.value()},
                    "error_message": "Value out of range.",
                }
            )
        if self._allowed_values_edit.text().strip():
            values = [value.strip() for value in self._allowed_values_edit.text().split(",") if value.strip()]
            rules.append(
                {
                    "rule_type": "set",
                    "rule_config": {"allowed": values},
                    "error_message": "Value not in allowed set.",
                }
            )
        self._result = rules
        super().accept()

    def _load_current(self) -> None:
        for rule in self._current:
            rule_type = rule.get("rule_type")
            config = rule.get("rule_config") or {}
            if rule_type == "required":
                self._required_checkbox.setChecked(True)
            elif rule_type == "regex":
                self._regex_edit.setText(config.get("pattern", ""))
            elif rule_type == "range":
                self._min_spin.setValue(int(config.get("min", 0)))
                self._max_spin.setValue(int(config.get("max", 0)))
            elif rule_type == "set":
                allowed = config.get("allowed", [])
                self._allowed_values_edit.setText(", ".join(str(value) for value in allowed))

