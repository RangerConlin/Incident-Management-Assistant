from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QPushButton, QTableWidget, QVBoxLayout, QWidget
from PySide6.QtQml import QQmlApplicationEngine


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
        """Open the detail dialog defined in QML."""
        engine = QQmlApplicationEngine()
        qml_path = Path(__file__).resolve().parents[1] / "qml" / "ObjectiveDetail.qml"
        engine.load(str(qml_path))
