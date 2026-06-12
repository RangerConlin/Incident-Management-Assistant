from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class TriageTracker(QWidget):
    def __init__(self, incident_id: str):
        super().__init__()
        self.incident_id = incident_id
        layout = QVBoxLayout(self)
        title = QLabel("Triage Tracker")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Legacy QML triage tracker has been removed."))
