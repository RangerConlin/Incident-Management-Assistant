"""Panel for logging safety incidents and near misses."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton


class SafetyIncidentsPanel(QWidget):
    """Placeholder incident log panel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Safety Incidents"))
        layout.addWidget(QPushButton("Record Incident"))
