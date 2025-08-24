"""PySide6 panel embedding ICS-214 QML."""
from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlApplicationEngine


def load_panel(engine: QQmlApplicationEngine) -> None:
    qml_path = Path(__file__).resolve().parent.parent / "qml" / "Ics214Home.qml"
    engine.load(QUrl.fromLocalFile(str(qml_path)))
