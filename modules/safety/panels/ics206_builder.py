from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ICS206Builder(QWidget):
    def __init__(self, incident_id: str):
        super().__init__()
        self.incident_id = incident_id
        layout = QVBoxLayout(self)
        title = QLabel("ICS-206 Builder")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Legacy QML ICS-206 builder has been removed."))
