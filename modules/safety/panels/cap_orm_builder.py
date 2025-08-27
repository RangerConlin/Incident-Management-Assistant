from pathlib import Path

from PySide6.QtCore import QObject
from PySide6.QtQml import QQmlApplicationEngine

QML_PATH = Path(__file__).resolve().parent.parent / "qml" / "CAPORMBuilder.qml"


class CapOrmBuilder(QObject):
    def __init__(self, incident_id: str):
        super().__init__()
        self.incident_id = incident_id
        self.engine = QQmlApplicationEngine(str(QML_PATH))
