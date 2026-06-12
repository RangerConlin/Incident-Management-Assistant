from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class FinanceHomePanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        title = QLabel("Finance Home")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Legacy QML finance home has been removed."))
