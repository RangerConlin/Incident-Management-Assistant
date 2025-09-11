"""Reusable widget helpers for the logistics module."""
from __future__ import annotations

from typing import Callable

from PySide6 import QtWidgets, QtGui, QtCore


class Toolbar(QtWidgets.QToolBar):
    """Small helper toolbar with common actions."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setIconSize(QtCore.QSize(16, 16))
        # TODO: load icons from central resources

    def add_action(self, text: str, slot: Callable[[], None], shortcut: str | None = None) -> QtGui.QAction:
        act = self.addAction(text)
        act.triggered.connect(slot)  # type: ignore[arg-type]
        if shortcut:
            act.setShortcut(QtGui.QKeySequence(shortcut))
        return act
