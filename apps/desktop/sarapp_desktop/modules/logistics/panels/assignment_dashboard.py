from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class AssignmentDashboard(QWidget):
    def __init__(self, incident_id: str):
        super().__init__()
        self.incident_id = incident_id
        self.setWindowTitle("Assignments")
        layout = QVBoxLayout(self)
        title = QLabel("Assignments")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Legacy QML assignment dashboard has been removed."))
