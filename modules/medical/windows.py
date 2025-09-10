from __future__ import annotations

import os
from typing import Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtQml import QQmlApplicationEngine, QQmlContext
from PySide6.QtCore import QObject, Property

from utils.state import AppState
from utils.app_signals import app_signals
from .panels import ICS206Panel

__all__ = ["get_206_panel", "open_206_window"]


# Keep strong refs so QML windows/bridges don't get GC'd
_engines: list[QQmlApplicationEngine] = []
_bridges: list[ICS206Panel] = []


class QmlAppState(QObject):
    """Minimal QML-facing wrapper exposing AppState values."""

    def __init__(self) -> None:
        super().__init__()
        self._activeIncident = str(AppState.get_active_incident() or "")
        op = AppState.get_active_op_period()
        self._activeOpPeriod = int(op) if op is not None else 0
        # React to global changes
        try:
            app_signals.incidentChanged.connect(self._on_incident)
            app_signals.opPeriodChanged.connect(self._on_op)
        except Exception:
            pass

    def _on_incident(self, number: str) -> None:
        self._activeIncident = number

    def _on_op(self, op: object) -> None:
        try:
            self._activeOpPeriod = int(op) if op is not None else 0
        except Exception:
            self._activeOpPeriod = 0

    def get_activeIncident(self) -> str:  # noqa: N802
        return self._activeIncident

    def get_activeOpPeriod(self) -> int:  # noqa: N802
        return self._activeOpPeriod

    activeIncident = Property(str, fget=get_activeIncident, constant=False)  # type: ignore[assignment]
    activeOpPeriod = Property(int, fget=get_activeOpPeriod, constant=False)  # type: ignore[assignment]


def open_206_window() -> QQmlApplicationEngine:
    """Open the floating, modeless ICS 206 QML ApplicationWindow.

    Returns the engine to allow optional external bookkeeping.
    """
    qml_path = os.path.abspath(os.path.join("modules", "medical", "qml", "ICS206Window.qml"))

    engine = QQmlApplicationEngine()
    ctx: QQmlContext = engine.rootContext()

    # Bridge for CRUD and pdf export signal
    bridge = ICS206Panel()
    try:
        from modules.safety.print_ics_206 import generate as generate_ics206_pdf

        def _on_pdf_requested():
            inc = AppState.get_active_incident()
            if not inc:
                return
            try:
                # Placeholder HTML content until a real template renderer is wired
                generate_ics206_pdf(str(inc), "<html><body>ICS 206</body></html>")
            except Exception:
                pass

        bridge.pdfRequested.connect(_on_pdf_requested)
    except Exception:
        pass

    # Expose to QML
    ctx.setContextProperty("ics206Bridge", bridge)
    ctx.setContextProperty("appState", QmlAppState())

    engine.load(qml_path)

    # Ensure the window is shown (QML has visible: true, but be defensive)
    roots = engine.rootObjects()
    if roots:
        try:
            roots[0].setProperty("visible", True)
        except Exception:
            pass

    _engines.append(engine)
    _bridges.append(bridge)
    return engine


def get_206_panel(incident_id: Optional[object] = None) -> QWidget:
    """Fallback QWidget placeholder for docking contexts.

    The main menu currently opens the full QML window via ``open_206_window``.
    This function remains for API compatibility.
    """
    w = QWidget()
    layout = QVBoxLayout(w)
    title_lbl = QLabel("Medical Plan (ICS-206)")
    title_lbl.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title_lbl)
    layout.addWidget(QLabel("The full ICS 206 opens as a separate window from the menu."))
    return w
