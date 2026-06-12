from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

__all__ = ["get_206_panel", "open_206_window"]


def get_206_panel(incident_id: Optional[object] = None) -> QWidget:
    """Return a dockable QWidget for the ICS-206 workspace."""

    widget = QWidget()
    layout = QVBoxLayout(widget)
    title = QLabel("Medical Plan (ICS-206)")
    title.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title)
    layout.addWidget(
        QLabel(
            "The legacy QML medical-plan window has been removed. "
            f"Use the widget-based medical workflow for incident: {incident_id}."
        )
    )
    return widget


def open_206_window(incident_id: Optional[object] = None) -> QWidget:
    """Compatibility wrapper for older callers expecting a separate window opener."""

    return get_206_panel(incident_id)
