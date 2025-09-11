from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class SitRepPanel(QWidget):
    """Placeholder panel for Situation Report."""

    def __init__(self, incident_id: object | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Situation Report")
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(f"SITREP — incident: {incident_id}")
        )


__all__ = ["SitRepPanel"]
