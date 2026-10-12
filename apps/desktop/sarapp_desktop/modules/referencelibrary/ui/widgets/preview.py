"""Preview pane widget."""

from PySide6.QtWidgets import QLabel


class PreviewWidget(QLabel):
    def __init__(self, parent=None):
        super().__init__("Select a document", parent)
