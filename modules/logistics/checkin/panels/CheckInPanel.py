"""Widget wrapper for the check-in interface without QML dependencies."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class CheckInPanel(QWidget):
    """Simple placeholder QWidget for check-in operations."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Check-In panel placeholder"))
