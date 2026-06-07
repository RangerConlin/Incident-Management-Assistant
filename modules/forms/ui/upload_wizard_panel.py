from __future__ import annotations

from typing import Any

from PySide6 import QtWidgets

class UploadWizardPanel(QtWidgets.QWidget):
    def __init__(self, upload_service: Any | None = None, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.upload_service = upload_service
        self.source_path = QtWidgets.QLineEdit(self)
        self.family_code = QtWidgets.QLineEdit(self)
        self.code = QtWidgets.QLineEdit(self)
        self.title = QtWidgets.QLineEdit(self)
        self.agency = QtWidgets.QLineEdit(self)
        self.system = QtWidgets.QLineEdit(self)
        self.create_button = QtWidgets.QPushButton("Create draft template", self)
        form = QtWidgets.QFormLayout(self)
        form.addRow("Source document", self.source_path)
        form.addRow("Family", self.family_code)
        form.addRow("Code", self.code)
        form.addRow("Title", self.title)
        form.addRow("Agency", self.agency)
        form.addRow("System", self.system)
        form.addRow(self.create_button)
