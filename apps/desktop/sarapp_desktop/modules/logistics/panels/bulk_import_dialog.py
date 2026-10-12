from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout


class BulkImportDialog(QDialog):
    def __init__(self, incident_id: str):
        super().__init__()
        self.incident_id = incident_id
        self.setWindowTitle("Bulk Import")
        layout = QVBoxLayout(self)
        title = QLabel("Bulk Import")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Legacy QML bulk import wizard has been removed."))
