# AUTO-GENERATED: Logistics module for Incident Management Assistant
# NOTE: Module code lives under /modules/logistics (not /backend).
"""Modeless dialog controller for resource request detail."""

from pathlib import Path

from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QDialog


class RequestDetailDialog(QDialog):
    def __init__(self, mission_id: str, request_id: int):
        super().__init__()
        self.mission_id = mission_id
        self.request_id = request_id
        self.setWindowTitle("Request Detail")
        engine = QQmlApplicationEngine()
        qml_path = Path(__file__).resolve().parents[1] / "qml" / "RequestDetail.qml"
        engine.load(str(qml_path))
