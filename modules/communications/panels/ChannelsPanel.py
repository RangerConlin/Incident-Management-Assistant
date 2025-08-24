"""Panel for managing the master channel library."""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ChannelsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Channels Panel"))
