from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

try:
    from .orm.ui.orm_window import ORMWindow
except Exception:  # pragma: no cover - fallback when ORM UI unavailable
    ORMWindow = None

__all__ = [
    "get_208_panel",
    "get_215A_panel",
    "get_caporm_panel",
    "get_safety_panel",
    "get_iwi_panel",
]


def _make_panel(title: str, body: str) -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title_lbl)
    layout.addWidget(QLabel(body))
    return w


def get_208_panel(incident_id: object | None = None) -> QWidget:
    """Return the ICS-208 Safety Message panel."""
    if incident_id is None:
        return _make_panel("Safety Message (ICS-208)", "Select an incident to edit the safety message.")
    try:
        from .panels.ics208_panel import ICS208Panel
        return ICS208Panel(incident_id=str(incident_id))
    except Exception:
        return _make_panel("Safety Message (ICS-208)", "ICS-208 panel unavailable in this environment.")


def get_215A_panel(incident_id: object | None = None) -> QWidget:
    """Return the ICS-215A Incident Action Safety Analysis panel."""
    if incident_id is None:
        return _make_panel(
            "Incident Action Safety Analysis (ICS-215A)",
            "Select an incident to view the safety analysis.",
        )
    try:
        from .panels.ics215a_panel import ICS215APanel
        return ICS215APanel(incident_id=str(incident_id))
    except Exception:
        return _make_panel(
            "Incident Action Safety Analysis (ICS-215A)",
            "ICS-215A panel unavailable in this environment.",
        )


def get_caporm_panel(incident_id: object | None = None) -> QWidget:
    """Return CAP ORM window, falling back to placeholder on error."""

    if ORMWindow is not None:
        try:
            return ORMWindow(incident_id=incident_id)
        except Exception:
            pass

    return _make_panel(
        "CAP ORM",
        "CAP ORM window unavailable in this environment.",
    )


def get_safety_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Safety Dashboard."""
    return _make_panel(
        "Safety Dashboard",
        f"Safety overview — incident: {incident_id}",
    )


def get_iwi_panel(incident_id: object | None = None) -> QWidget:
    """Return the Safety Incident (IWI) dashboard panel."""
    if incident_id is None:
        return _make_panel("Safety Incidents", "Select an incident to view safety incident reports.")
    try:
        from .panels.iwi_dashboard import IWIDashboard
        return IWIDashboard(str(incident_id))
    except Exception:
        return _make_panel("Safety Incidents", "Safety Incident dashboard unavailable in this environment.")


# Note: weather panel removed.


# No weather controller; weather submodule removed.
