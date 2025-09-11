from __future__ import annotations
from typing import Optional
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from utils.state import AppState
from utils.app_signals import app_signals
from .panels import ICS206Window
from bridge.ics206_bridge import Ics206Bridge

__all__ = ["get_206_panel", "open_206_window", "open_206_widget_window"]


def open_206_window() -> ICS206Window:
    """Open the QtWidgets based ICS 206 window."""
    bridge = Ics206Bridge()
    bridge.ensure_ics206_tables()

    class _State:
        incident_name = str(AppState.get_active_incident() or "")
        op_period_display = str(AppState.get_active_op_period() or "")

    win = ICS206Window(bridge, _State())
    win.show()
    return win


def open_206_widget_window() -> ICS206Window:
    """Open the QtWidgets based ICS 206 window."""
    bridge = Ics206Bridge()
    bridge.ensure_ics206_tables()
    class _State:
        incident_name = str(AppState.get_active_incident() or "")
        op_period_display = str(AppState.get_active_op_period() or "")
    win = ICS206Window(bridge, _State())
    win.show()
    return win


def get_206_panel(incident_id: Optional[object] = None) -> QWidget:
    """Fallback QWidget placeholder for docking contexts.

    The main menu opens the full window via :func:`open_206_window`.
    """
    w = QWidget()
    layout = QVBoxLayout(w)
    title_lbl = QLabel("Medical Plan (ICS-206)")
    title_lbl.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title_lbl)
    layout.addWidget(QLabel("The full ICS 206 opens as a separate window from the menu."))
    return w
