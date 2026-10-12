"""QtWidgets implementation of the Logistics ICS-211 panel."""
from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from ..widgets import ICS211CheckInWindow


class CheckInPanel(QWidget):
    """Container that embeds the full ICS-211 workbench in a dock/widget."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.window = ICS211CheckInWindow(self)
        layout.addWidget(self.window)
