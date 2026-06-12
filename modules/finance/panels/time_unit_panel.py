from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class TimeUnitPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        title = QLabel("Time Unit")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Legacy QML time-unit screen has been removed."))
