"""Signatures page."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QPushButton
)


class SignaturesPage(QWidget):
    def __init__(self, bridge, parent=None) -> None:
        super().__init__(parent)
        self.bridge = bridge
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.prepared_by = QLineEdit()
        self.prepared_pos = QLineEdit()
        self.approved_by = QLineEdit()
        self.signed_at = QLineEdit()
        form.addRow("Prepared By", self.prepared_by)
        form.addRow("Position", self.prepared_pos)
        form.addRow("Approved By", self.approved_by)
        form.addRow("Signed At", self.signed_at)
        layout.addLayout(form)

        btn_row = QVBoxLayout()
        self.btn_publish = QPushButton("Publish to OP Period")
        self.btn_pdf = QPushButton("PDF")
        self.btn_save = QPushButton("Save")
        btn_row.addWidget(self.btn_publish)
        btn_row.addWidget(self.btn_pdf)
        btn_row.addWidget(self.btn_save)
        layout.addLayout(btn_row)

        self.btn_save.clicked.connect(self.on_save)

        self.reload()

    def reload(self) -> None:
        data = self.bridge.get_signatures()
        self.prepared_by.setText(data.get("prepared_by", ""))
        self.prepared_pos.setText(data.get("prepared_position", ""))
        self.approved_by.setText(data.get("approved_by", ""))
        self.signed_at.setText(data.get("signed_at", ""))

    def on_save(self) -> None:
        self.bridge.save_signatures(
            {
                "prepared_by": self.prepared_by.text(),
                "prepared_position": self.prepared_pos.text(),
                "approved_by": self.approved_by.text(),
                "signed_at": self.signed_at.text(),
            }
        )
