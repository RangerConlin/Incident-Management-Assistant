from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class LogisticsHomePanel(QWidget):
    """Widget-native landing panel for Logistics."""

    def __init__(self, incident_id: str | None = None):
        super().__init__()
        self.setObjectName("LogisticsHomePanel")
        self.setWindowTitle("Logistics Dashboard")

        layout = QVBoxLayout(self)
        title = QLabel("Logistics Dashboard")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Legacy QML logistics quick actions have been removed."))
        if incident_id:
            layout.addWidget(QLabel(f"Active incident: {incident_id}"))
