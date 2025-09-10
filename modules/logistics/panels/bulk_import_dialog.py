# AUTO-GENERATED: Logistics module for Incident Management Assistant
# NOTE: Module code lives under /modules/logistics (not /backend).
"""Bulk import wizard dialog using standard widgets."""

from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout


class BulkImportDialog(QDialog):
    def __init__(self, incident_id: str):
        super().__init__()
        self.incident_id = incident_id
        self.setWindowTitle("Bulk Import")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Bulk import wizard placeholder"))
