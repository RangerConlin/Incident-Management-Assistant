"""Alerts + HWO tab — advisories with acknowledge button, plus HWO text."""

from __future__ import annotations

import logging
from typing import List, Optional

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...models.advisory import Advisory
from ...models.location import WeatherLocation
from ...services import weather_repository_client as client
from ...services.weather_manager import WeatherManager
from ..widgets.severity_badge import SeverityBadge

LOGGER = logging.getLogger(__name__)


class _AdvisoryCard(QFrame):
    def __init__(self, incident_id: str, advisory: Advisory, notification: Optional[dict], parent=None):
        super().__init__(parent)
        self._incident_id = incident_id
        self._advisory = advisory
        self._notification = notification
        self.setFrameShape(QFrame.StyledPanel)

        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        title = QLabel(advisory.event or "Advisory")
        title.setStyleSheet("font-weight: 700;")
        header.addWidget(title)
        header.addWidget(SeverityBadge(advisory.severity or "unknown", (advisory.severity or "unknown").lower()))
        layout.addLayout(header)

        desc = QLabel(advisory.headline or advisory.description or "")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        footer = QHBoxLayout()
        if notification and notification.get("acknowledged_at"):
            ack = QLabel(f"✓ Acknowledged — {notification.get('acknowledged_by', '')}, {notification.get('acknowledged_at', '')}")
            ack.setStyleSheet("color: #1f7a52; font-weight: 600;")
            footer.addWidget(ack)
        elif notification:
            btn = QPushButton("Acknowledge")
            btn.clicked.connect(self._acknowledge)
            footer.addWidget(btn)
        layout.addLayout(footer)

    def _acknowledge(self) -> None:
        notification_id = self._notification.get("notification_id") if self._notification else None
        if notification_id is None:
            return
        try:
            client.acknowledge_weather_alert(self._incident_id, notification_id, acknowledged_by="")
        except Exception:
            LOGGER.exception("Failed to acknowledge weather alert %s", notification_id)


class AlertsHwoTab(QWidget):
    def __init__(self, manager: WeatherManager, incident_id: str, parent=None):
        super().__init__(parent)
        self._manager = manager
        self._incident_id = incident_id
        self._location: Optional[WeatherLocation] = None

        layout = QHBoxLayout(self)

        left = QVBoxLayout()
        left.addWidget(QLabel("Active advisories"))
        self._alerts_scroll = QScrollArea()
        self._alerts_scroll.setWidgetResizable(True)
        self._alerts_content = QWidget()
        self._alerts_layout = QVBoxLayout(self._alerts_content)
        self._alerts_scroll.setWidget(self._alerts_content)
        left.addWidget(self._alerts_scroll)
        layout.addLayout(left, 1)

        right = QVBoxLayout()
        right.addWidget(QLabel("Hazardous Weather Outlook"))
        self._hwo_text = QTextEdit()
        self._hwo_text.setReadOnly(True)
        right.addWidget(self._hwo_text)
        layout.addLayout(right, 1)

        manager.alertsUpdated.connect(self._on_alerts)
        manager.hwoUpdated.connect(self._on_hwo)

    def set_location(self, location: Optional[WeatherLocation]) -> None:
        self._location = location
        if location is not None:
            snap = self._manager.snapshot(location.location_id)
            if snap:
                self._render_alerts(snap.advisories)
                self._hwo_text.setPlainText(snap.hwo_text or "No hazardous weather outlook available.")

    def _on_alerts(self, location_id: str, advisories: List[Advisory]) -> None:
        if self._location and location_id == self._location.location_id:
            self._render_alerts(advisories)

    def _on_hwo(self, location_id: str, text: str) -> None:
        if self._location and location_id == self._location.location_id:
            self._hwo_text.setPlainText(text or "No hazardous weather outlook available.")

    def _render_alerts(self, advisories: List[Advisory]) -> None:
        while self._alerts_layout.count():
            item = self._alerts_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not advisories:
            self._alerts_layout.addWidget(QLabel("No active advisories."))
            return

        try:
            notifications = client.list_weather_alerts(self._incident_id)
        except Exception:
            LOGGER.exception("Failed to load weather alert acknowledgement state")
            notifications = []
        by_key = {n.get("source_id"): n for n in notifications}

        for advisory in advisories:
            key = f"{advisory.event}|{advisory.headline}|{advisory.start}"
            card = _AdvisoryCard(self._incident_id, advisory, by_key.get(key))
            self._alerts_layout.addWidget(card)
        self._alerts_layout.addStretch(1)


__all__ = ["AlertsHwoTab"]
