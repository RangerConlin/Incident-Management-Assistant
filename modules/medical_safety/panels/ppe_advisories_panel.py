"""Panel for managing PPE advisories."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton


class PpeAdvisoriesPanel(QWidget):
    """Placeholder PPE panel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("PPE Advisories"))
        layout.addWidget(QPushButton("Add Advisory"))
