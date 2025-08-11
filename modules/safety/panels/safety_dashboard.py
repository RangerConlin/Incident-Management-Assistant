from pathlib import Path

from PySide6.QtCore import QObject
from PySide6.QtQml import QQmlApplicationEngine

QML_PATH = Path(__file__).resolve().parent.parent / "qml" / "SafetyDashboard.qml"


class SafetyDashboard(QObject):
    """Main dashboard combining safety reports and medical incidents."""

    def __init__(self, mission_id: str):
        super().__init__()
        self.mission_id = mission_id
        self.engine = QQmlApplicationEngine(str(QML_PATH))
