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
    "get_weather_panel",
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
    """Return placeholder QWidget for Safety Plan (ICS-208)."""
    return _make_panel(
        "Safety Plan (ICS-208)",
        f"ICS-208 form — incident: {incident_id}",
    )


def get_215A_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Incident Action Safety Analysis (ICS-215A)."""
    return _make_panel(
        "Incident Action Safety Analysis (ICS-215A)",
        f"ICS-215A form — incident: {incident_id}",
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


def get_weather_panel(incident_id: object | None = None) -> QWidget:
    """Return Weather Summary panel for Safety module."""
    try:
        from .weather.ui.summary_panel import WeatherSummaryPanel

        return WeatherSummaryPanel()
    except Exception:
        return _make_panel(
            "Weather Safety",
            f"Weather safety panel unavailable — incident: {incident_id}",
        )
