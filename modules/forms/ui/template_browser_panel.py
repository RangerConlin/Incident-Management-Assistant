from __future__ import annotations

from typing import Any

from PySide6 import QtWidgets

class TemplateBrowserPanel(QtWidgets.QWidget):
    def __init__(self, template_service: Any | None = None, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.template_service = template_service
        self.search = QtWidgets.QLineEdit(self)
        self.search.setPlaceholderText("Search forms")
        self.agency_filter = QtWidgets.QLineEdit(self)
        self.agency_filter.setPlaceholderText("Agency or system")
        self.family_filter = QtWidgets.QLineEdit(self)
        self.family_filter.setPlaceholderText("Form family")
        self.status_filter = QtWidgets.QComboBox(self)
        self.status_filter.addItems(["active", "draft", "retired", "all"])
        self.table = QtWidgets.QTableWidget(0, 5, self)
        self.table.setHorizontalHeaderLabels(["Family", "Agency", "System", "Code", "Version"])
        self.create_instance_button = QtWidgets.QPushButton("Create instance", self)
        self.manager_button = QtWidgets.QPushButton("Open template manager", self)
        top = QtWidgets.QHBoxLayout()
        for widget in (self.search, self.family_filter, self.agency_filter, self.status_filter):
            top.addWidget(widget)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(self.create_instance_button)
        buttons.addWidget(self.manager_button)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.table)
        layout.addLayout(buttons)

    def load_templates(self, templates: list[dict[str, Any]]) -> None:
        self.table.setRowCount(len(templates))
        for row, item in enumerate(templates):
            values = [item.get("family_code", ""), item.get("agency", ""), item.get("system", ""), item.get("code", ""), str(item.get("current_version_id") or "")]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QtWidgets.QTableWidgetItem(value))
