from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ObjectivesPanel(QWidget):
    """Placeholder panel for Objectives."""

    def __init__(self, incident_id: object | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Objectives")
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(f"Objectives for the incident — incident: {incident_id}")
        )


__all__ = ["ObjectivesPanel"]
