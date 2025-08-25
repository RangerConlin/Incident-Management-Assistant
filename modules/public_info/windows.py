from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

__all__ = [
    "get_media_releases_panel",
    "get_inquiries_panel",
    "get_public_info_panel",
]

def _make_panel(title: str, body: str) -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title_lbl)
    layout.addWidget(QLabel(body))
    return w

def get_media_releases_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Media Releases."""
    return _make_panel(
        "Media Releases",
        f"Draft and publish releases — mission: {mission_id}",
    )

def get_inquiries_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Public Inquiries."""
    return _make_panel(
        "Public Inquiries",
        f"Track inquiries — mission: {mission_id}",
    )

def get_public_info_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Public Information dashboard."""
    return _make_panel(
        "Public Information Dashboard",
        f"Public information overview — mission: {mission_id}",
    )
