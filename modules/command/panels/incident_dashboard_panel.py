from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from PySide6QtAds import CDockWidget


class IncidentDashboardPanel(CDockWidget):
    """Dockable Incident Dashboard panel without QML."""

    def __init__(self, parent=None) -> None:
        super().__init__("Incident Dashboard — Command", parent)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(
            QLabel("Incident dashboard functionality is pending implementation.")
        )

        self.setWidget(container)


__all__ = ["IncidentDashboardPanel"]

