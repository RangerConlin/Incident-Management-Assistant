from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QLineEdit


class SearchLineEdit(QLineEdit):
    """Line edit with placeholder and shortcut for search/filter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Search…")
        self.shortcut = QKeySequence.Find

    def setShortcut(self, seq: QKeySequence) -> None:  # pragma: no cover - trivial
        self.shortcut = seq

