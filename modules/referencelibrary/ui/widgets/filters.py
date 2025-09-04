"""Filters panel widget."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget


class FiltersWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Categories"))
        self.category_list = QListWidget()
        layout.addWidget(self.category_list)
        layout.addStretch()
