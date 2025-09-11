"""Panel for recording safety briefings."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton


class SafetyBriefingsPanel(QWidget):
    """Placeholder briefings panel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Safety Briefings"))
        layout.addWidget(QPushButton("Record Briefing"))
