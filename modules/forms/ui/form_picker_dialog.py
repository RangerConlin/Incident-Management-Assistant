from __future__ import annotations

from typing import Any

from PySide6 import QtWidgets

class FormPickerDialog(QtWidgets.QDialog):
    def __init__(self, templates: list[dict[str, Any]] | None = None, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Choose form output")
        self.group_filter = QtWidgets.QLineEdit(self)
        self.group_filter.setPlaceholderText("Group similar form types")
        self.list_widget = QtWidgets.QListWidget(self)
        self.buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel, self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.group_filter)
        layout.addWidget(self.list_widget)
        layout.addWidget(self.buttons)
        for template in templates or []:
            self.list_widget.addItem(f"{template.get('family_code', template.get('code', ''))} - {template.get('agency', '')}")
