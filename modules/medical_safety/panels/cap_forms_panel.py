"""Panel for listing and managing CAP forms."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton


class CapFormsPanel(QWidget):
    """Placeholder CAP forms browser."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("CAP Forms"))
        layout.addWidget(QPushButton("New CAP Form"))
