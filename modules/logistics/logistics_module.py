"""Entry point for the QtWidgets based logistics module."""
from __future__ import annotations

from PySide6 import QtWidgets

from .panels.logistics_home_panel import LogisticsHomePanel


def get_panel(parent: QtWidgets.QWidget | None = None) -> LogisticsHomePanel:
    """Return the main logistics panel widget."""
    return LogisticsHomePanel(parent)
