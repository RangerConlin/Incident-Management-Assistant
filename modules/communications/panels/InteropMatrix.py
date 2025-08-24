"""Panel showing interoperability matrix across bands."""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class InteropMatrix(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Interop Matrix"))
