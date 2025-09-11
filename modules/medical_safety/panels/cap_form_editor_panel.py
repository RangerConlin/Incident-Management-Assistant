"""Schema-driven CAP form editor panel."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton


class CapFormEditorPanel(QWidget):
    """Very small form editor that uses JSON schema conceptually."""

    def __init__(self, schema: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("CAP Form Editor"))
        layout.addWidget(QTextEdit())
        layout.addWidget(QPushButton("Validate"))
