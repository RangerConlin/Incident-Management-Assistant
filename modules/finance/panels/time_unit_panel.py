from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QWidget, QVBoxLayout


class TimeUnitPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.view = QQuickWidget()
        qml_file = Path(__file__).resolve().parent.parent / "qml" / "TimeUnit.qml"
        self.view.setSource(QUrl.fromLocalFile(str(qml_file)))
        self.view.setResizeMode(QQuickWidget.SizeRootObjectToView)
        layout.addWidget(self.view)
