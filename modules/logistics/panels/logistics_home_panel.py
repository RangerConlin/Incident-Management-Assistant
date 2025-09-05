# AUTO-GENERATED: Logistics module for Incident Management Assistant
# NOTE: Module code lives under /modules/logistics (not /backend).
"""Logistics dashboard home panel with quick access actions.

This panel is intentionally lightweight but demonstrates how a real
implementation would embed a QML component providing buttons for common
logistics tasks.  The panel is safe to import when Qt is not available; in
such scenarios a simple placeholder widget is returned.
"""

from __future__ import annotations

from pathlib import Path

try:  # pragma: no cover - UI is not exercised in tests
    from PySide6.QtCore import QUrl
    from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
    from PySide6.QtQuickWidgets import QQuickWidget
except Exception:  # pragma: no cover - Qt is unavailable
    QLabel = QVBoxLayout = QWidget = object  # type: ignore
    QQuickWidget = None  # type: ignore


class LogisticsHomePanel(QWidget):
    """Top level dashboard for the Logistics section.

    The widget embeds ``LogisticsQuickActions.qml`` which renders a column of
    push buttons for frequently performed actions like raising a requisition or
    opening the equipment board.  When the Qt libraries are not installed the
    panel degrades gracefully to a simple label making it safe to import in a
    headless environment.
    """

    def __init__(self, incident_id: str | None = None):
        super().__init__()
        self.setObjectName("LogisticsHomePanel")
        self.setWindowTitle("Logistics Dashboard")

        layout = QVBoxLayout(self)

        if QQuickWidget is None:  # Qt not present – placeholder text only
            layout.addWidget(QLabel("QtQuick not available"))
            return

        qml_widget = QQuickWidget()
        qml_widget.setResizeMode(QQuickWidget.SizeRootObjectToView)
        qml_path = Path(__file__).resolve().parent.parent / "qml" / "LogisticsQuickActions.qml"
        qml_widget.setSource(QUrl.fromLocalFile(qml_path.as_posix()))
        layout.addWidget(qml_widget)

        if incident_id:
            # Simple heading indicating the active incident; real implementation
            # would show KPIs here.
            layout.addWidget(QLabel(f"Active incident: {incident_id}"))

