"""Panel for displaying and editing the hazard log."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class HazardLogPanel(QWidget):
    """Placeholder hazard log panel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Hazard Log"))
