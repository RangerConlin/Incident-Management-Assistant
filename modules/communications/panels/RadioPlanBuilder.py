"""Panel for editing operational period radio plans."""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class RadioPlanBuilder(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Radio Plan Builder"))
