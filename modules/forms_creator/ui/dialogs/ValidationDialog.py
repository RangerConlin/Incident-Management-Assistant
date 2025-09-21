"""Dialog to configure field validation rules."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)


class ValidationDialog(QDialog):
    """Collects simple validation rules (required + regex)."""

    def __init__(self, config: dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Field Validations")
        self.validations: list[dict[str, Any]] = config.get("validations", []).copy()
        self._required_message: str | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.required_check = QCheckBox("Field is required")
        form.addRow(self.required_check)

        self.regex_edit = QLineEdit()
        self.regex_edit.setPlaceholderText("Regular expression pattern")
        form.addRow("Regex", self.regex_edit)

        self.regex_message_edit = QLineEdit()
        self.regex_message_edit.setPlaceholderText("Error message when regex fails")
        form.addRow("Regex Message", self.regex_message_edit)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(button_box)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        self._load_initial_state()

    def _load_initial_state(self) -> None:
        for rule in self.validations:
            if rule.get("rule_type") == "required":
                self.required_check.setChecked(True)
                self._required_message = rule.get("error_message")
            elif rule.get("rule_type") == "regex":
                config = rule.get("rule_config", {})
                self.regex_edit.setText(config.get("pattern", ""))
                self.regex_message_edit.setText(rule.get("error_message", ""))

    def accept(self) -> None:  # noqa: D401
        result: list[dict[str, Any]] = []
        if self.required_check.isChecked():
            result.append(
                {
                    "rule_type": "required",
                    "rule_config": {},
                    "error_message": self._required_message or "Required field",
                }
            )
        pattern = self.regex_edit.text().strip()
        if pattern:
            result.append(
                {
                    "rule_type": "regex",
                    "rule_config": {"pattern": pattern},
                    "error_message": self.regex_message_edit.text().strip() or "Invalid format",
                }
            )
        self.validations = result
        super().accept()
