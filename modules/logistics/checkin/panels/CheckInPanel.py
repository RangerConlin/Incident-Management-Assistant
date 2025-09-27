"""QtWidgets implementation of the Logistics Check-In panel."""
from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from ..widgets import CheckInWindow


class CheckInPanel(QWidget):
    """Container that embeds :class:`CheckInWindow` in a dock/widget."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.window = CheckInWindow(self)
        layout.addWidget(self.window)
