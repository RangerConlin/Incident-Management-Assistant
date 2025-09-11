"""ICS 208 Safety Message editor panel."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton


class SafetyMessagePanel(QWidget):
    """Simple editor for ICS 208 message."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("ICS 208 Safety Message"))
        layout.addWidget(QTextEdit())
        layout.addWidget(QPushButton("Save"))
