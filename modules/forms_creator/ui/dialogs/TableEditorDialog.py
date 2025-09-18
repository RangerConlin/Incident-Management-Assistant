"""Placeholder dialog for configuring table/repeater fields."""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QTextEdit, QVBoxLayout


class TableEditorDialog(QDialog):
    """Stub implementation that allows capturing simple notes."""

    def __init__(self, current: dict[str, Any] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Table Field Configuration")
        self._notes_edit = QTextEdit()
        self._notes_edit.setPlaceholderText("Describe the table layout, columns and sample data here.")
        if current and current.get("notes"):
            self._notes_edit.setText(str(current["notes"]))

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "This version of the Form Creator captures table configuration notes only. "
                "Future releases will translate these notes into interactive column definitions."
            )
        )
        layout.addWidget(self._notes_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._result = current or {}

    @property
    def table_config(self) -> dict[str, Any]:
        result = dict(self._result)
        result["notes"] = self._notes_edit.toPlainText().strip()
        return result

