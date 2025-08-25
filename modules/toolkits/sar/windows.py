from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

__all__ = ["get_missing_person_panel", "get_pod_panel"]

def _make_panel(title: str, body: str) -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title_lbl)
    layout.addWidget(QLabel(body))
    return w

def get_missing_person_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Missing Person Report."""
    return _make_panel(
        "Missing Person Report",
        f"Record missing person data — mission: {mission_id}",
    )

def get_pod_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Probability of Detection (POD)."""
    return _make_panel(
        "Probability of Detection",
        f"POD calculator — mission: {mission_id}",
    )
