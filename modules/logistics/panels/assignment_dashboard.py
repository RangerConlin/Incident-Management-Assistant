# AUTO-GENERATED: Logistics module for Incident Management Assistant
# NOTE: Module code lives under /modules/logistics (not /backend).
"""Assignment dashboard panel."""

from pathlib import Path

from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QWidget


class AssignmentDashboard(QWidget):
    def __init__(self, mission_id: str):
        super().__init__()
        self.mission_id = mission_id
        self.setWindowTitle("Assignments")
        engine = QQmlApplicationEngine()
        qml_path = Path(__file__).resolve().parents[1] / "qml" / "AssignmentDashboard.qml"
        engine.load(str(qml_path))
