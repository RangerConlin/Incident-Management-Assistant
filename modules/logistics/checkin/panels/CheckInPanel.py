"""Optional widget wrapper to host the QML check-in window."""
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtQml import QQmlEngine

from ..checkin_bridge import CheckInBridge


class CheckInPanel(QWidget):
    """Simple QWidget that loads the QML CheckInWindow."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.bridge = CheckInBridge()
        self.view = QQuickWidget()
        self.view.engine().rootContext().setContextProperty("checkInBridge", self.bridge)
        self.view.setSource("modules/logistics/checkin/qml/CheckInWindow.qml")
        layout.addWidget(self.view)
