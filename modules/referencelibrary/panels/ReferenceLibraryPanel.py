"""Controller for the main Reference Library panel."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QObject


class ReferenceLibraryPanel(QObject):
    """Minimal controller that loads the ReferenceLibrary.qml view."""

    def __init__(self) -> None:
        super().__init__()
        self.engine = QQmlApplicationEngine()
        qml_path = Path(__file__).resolve().parents[1] / "qml" / "ReferenceLibrary.qml"
        self.engine.load(str(qml_path))
