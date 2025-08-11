"""Controller for managing collections in the reference library."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject
from PySide6.QtQml import QQmlApplicationEngine


class CollectionsManager(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.engine = QQmlApplicationEngine()
        qml_path = Path(__file__).resolve().parents[1] / "qml" / "CollectionsManager.qml"
        self.engine.load(str(qml_path))
