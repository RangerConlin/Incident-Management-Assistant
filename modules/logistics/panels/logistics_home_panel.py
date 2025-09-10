# AUTO-GENERATED: Logistics module for Incident Management Assistant
# NOTE: Module code lives under /modules/logistics (not /backend).
"""Logistics dashboard home panel with quick access actions.

This panel is intentionally lightweight but previously demonstrated how a real
implementation could embed a QML component providing buttons for common
logistics tasks.  The QML dependency made the widget unusable in headless test
environments so the panel now relies solely on standard Qt widgets.  It is safe
to import even when Qt's Quick/QML modules are unavailable.
"""

from __future__ import annotations

try:  # pragma: no cover - UI is not exercised in tests
    from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget, QPushButton
except Exception:  # pragma: no cover - Qt is unavailable
    QLabel = QVBoxLayout = QWidget = QPushButton = object  # type: ignore


class LogisticsHomePanel(QWidget):
    """Top level dashboard for the Logistics section.

    The widget presents a set of push buttons for frequently performed actions
    like raising a requisition or opening the equipment board.  The previous
    implementation embedded a QML scene to render these controls, however the
    test environment does not provide the required Qt Quick libraries.  By
    using only traditional widgets the panel now degrades gracefully and
    remains safe to import in headless environments.
    """

    def __init__(self, incident_id: str | None = None):
        super().__init__()
        self.setObjectName("LogisticsHomePanel")
        self.setWindowTitle("Logistics Dashboard")

        layout = QVBoxLayout(self)

        # Basic quick-action buttons that previously lived in a QML scene.
        for label in [
            "New Request",
            "Equipment Board",
            "Check-In",
        ]:
            btn = QPushButton(label)
            layout.addWidget(btn)

        if incident_id:
            # Simple heading indicating the active incident; real implementation
            # would show KPIs here.
            layout.addWidget(QLabel(f"Active incident: {incident_id}"))

