from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QPushButton, QTableWidget, QVBoxLayout, QWidget


class ObjectivesPanel(QWidget):
    """Simple table panel listing incident objectives."""

    def __init__(self, mission_id: int):
        super().__init__()
        self.mission_id = mission_id
        self.setWindowTitle("Objectives")

        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        layout.addWidget(self.table)

        self.new_btn = QPushButton("New Objective")
        layout.addWidget(self.new_btn)
        self.new_btn.clicked.connect(self.open_detail)

    def open_detail(self) -> None:
        QMessageBox.information(
            self,
            "Objectives",
            "The legacy QML objective detail dialog has been removed.",
        )
