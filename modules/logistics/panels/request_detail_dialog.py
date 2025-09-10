# AUTO-GENERATED: Logistics module for Incident Management Assistant
# NOTE: Module code lives under /modules/logistics (not /backend).
"""Modeless dialog controller for resource request detail."""

from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout


class RequestDetailDialog(QDialog):
    def __init__(self, incident_id: str, request_id: int):
        super().__init__()
        self.incident_id = incident_id
        self.request_id = request_id
        self.setWindowTitle("Request Detail")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Request detail placeholder for {request_id}"))
