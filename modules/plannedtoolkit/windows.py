from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

__all__ = [
    "get_promotions_panel",
    "get_vendors_panel",
    "get_safety_panel",
    "get_tasking_panel",
    "get_health_sanitation_panel",
    "get_planned_toolkit_panel",
]


def _make_panel(title: str, body: str) -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title_lbl)
    layout.addWidget(QLabel(body))
    return w


def get_promotions_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for External Messaging."""
    return _make_panel(
        "External Messaging",
        f"Promotions — incident: {incident_id}",
    )


def get_vendors_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Vendors & Permits."""
    return _make_panel(
        "Vendors & Permits",
        f"Vendors — incident: {incident_id}",
    )


def get_safety_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Public Safety."""
    return _make_panel(
        "Public Safety",
        f"Safety — incident: {incident_id}",
    )


def get_tasking_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Tasking & Assignments."""
    return _make_panel(
        "Tasking & Assignments",
        f"Tasking — incident: {incident_id}",
    )


def get_health_sanitation_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Health & Sanitation."""
    return _make_panel(
        "Health & Sanitation",
        f"Health & sanitation — incident: {incident_id}",
    )


def get_planned_toolkit_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Planned Event Toolkit."""
    return _make_panel(
        "Planned Event Toolkit",
        f"Toolkit — incident: {incident_id}",
    )

