from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class IncidentOverviewPanel(QWidget):
    """Placeholder panel for Incident Overview."""

    def __init__(self, incident_id: object | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Incident Overview")
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(f"Overview of the incident — incident: {incident_id}")
        )


__all__ = ["IncidentOverviewPanel"]
