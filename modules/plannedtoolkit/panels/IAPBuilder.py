from __future__ import annotations

from PySide6.QtWidgets import QWidget
from . import _load_qml


class IAPBuilder(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _load_qml(self, "IAPBuilder.qml")
