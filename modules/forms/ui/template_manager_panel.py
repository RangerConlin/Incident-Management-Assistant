from __future__ import annotations

from typing import Any

from PySide6 import QtWidgets

class TemplateManagerPanel(QtWidgets.QWidget):
    def __init__(self, template_service: Any | None = None, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.template_service = template_service
        self.template_list = QtWidgets.QListWidget(self)
        self.metadata = QtWidgets.QFormLayout()
        self.code_edit = QtWidgets.QLineEdit(self)
        self.title_edit = QtWidgets.QLineEdit(self)
        self.agency_edit = QtWidgets.QLineEdit(self)
        self.metadata.addRow("Code", self.code_edit)
        self.metadata.addRow("Title", self.title_edit)
        self.metadata.addRow("Agency", self.agency_edit)
        self.version_list = QtWidgets.QListWidget(self)
        self.fields = QtWidgets.QTableWidget(0, 4, self)
        self.fields.setHorizontalHeaderLabels(["Key", "Label", "Type", "Binding"])
        self.warning_box = QtWidgets.QTextEdit(self)
        self.warning_box.setReadOnly(True)
        self.save_button = QtWidgets.QPushButton("Save new version", self)
        right = QtWidgets.QVBoxLayout()
        right.addLayout(self.metadata)
        right.addWidget(QtWidgets.QLabel("Versions", self))
        right.addWidget(self.version_list)
        right.addWidget(QtWidgets.QLabel("Fields", self))
        right.addWidget(self.fields)
        right.addWidget(self.warning_box)
        right.addWidget(self.save_button)
        layout = QtWidgets.QHBoxLayout(self)
        layout.addWidget(self.template_list, 1)
        layout.addLayout(right, 3)
