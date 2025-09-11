"""Special Medical Procedures page."""
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QPlainTextEdit, QPushButton


class ProceduresPage(QWidget):
    def __init__(self, bridge, parent=None) -> None:
        super().__init__(parent)
        self.bridge = bridge
        layout = QVBoxLayout(self)

        self.text = QPlainTextEdit()
        self.text.setPlaceholderText("Enter special medical procedures…")
        layout.addWidget(self.text, 1)

        self.btn_save = QPushButton("Save Procedures")
        layout.addWidget(self.btn_save)

        self.btn_save.clicked.connect(self.on_save)

        self.reload()

    def reload(self) -> None:
        data = self.bridge.get_procedures()
        self.text.setPlainText(data.get("notes", ""))

    def on_save(self) -> None:
        self.bridge.save_procedures(self.text.toPlainText())
