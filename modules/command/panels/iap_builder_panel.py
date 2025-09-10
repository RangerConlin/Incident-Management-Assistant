from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class IAPBuilderPanel(QWidget):
    """Placeholder panel for the IAP Builder."""

    def __init__(self, incident_id: object | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("IAP Builder")
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(f"Build an Incident Action Plan — incident: {incident_id}")
        )


__all__ = ["IAPBuilderPanel"]
