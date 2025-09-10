from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class StaffOrgPanel(QWidget):
    """Placeholder panel for Staff Organization."""

    def __init__(self, incident_id: object | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Staff Organization")
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(f"Staff organization details — incident: {incident_id}")
        )


__all__ = ["StaffOrgPanel"]
