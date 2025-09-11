"""Safety dashboard panel showing quick safety overview."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class SafetyDashboardPanel(QWidget):
    """Minimal dashboard placeholder."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Safety Dashboard"))
