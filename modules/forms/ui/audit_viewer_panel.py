from __future__ import annotations

from typing import Any

from PySide6 import QtWidgets

class AuditViewerPanel(QtWidgets.QWidget):
    def __init__(self, audit_service: Any | None = None, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.audit_service = audit_service
        self.audit_table = QtWidgets.QTableWidget(0, 5, self)
        self.audit_table.setHorizontalHeaderLabels(["Time", "Action", "Field", "User", "Details"])
        self.revision_list = QtWidgets.QListWidget(self)
        splitter = QtWidgets.QSplitter(self)
        splitter.addWidget(self.audit_table)
        splitter.addWidget(self.revision_list)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(splitter)
