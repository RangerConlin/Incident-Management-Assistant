"""Frameless alert toast window."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..services.alerts import alert_center
from ..infra import ui_factories


class AlertToast(QWidget):
    """Transient toast for severe weather alerts."""

    def __init__(self, payload: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("alertToast")
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self._drag_pos: QPoint | None = None
        self.payload = payload or {}
        self._setup_ui()
        self._bind_payload()

    def _setup_ui(self) -> None:
        container = QFrame(self)
        container.setObjectName("alertToastFrame")
        container.setStyleSheet(
            "background-color: palette(base); border: 1px solid palette(highlight);"
        )
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        self.headline = QLabel("⚠ Weather Alert", container)
        self.headline.setAccessibleName("Alert Headline")
        self.headline.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.headline)

        self.details = QLabel("Details unavailable.", container)
        self.details.setAccessibleName("Alert Details")
        self.details.setWordWrap(True)
        layout.addWidget(self.details)

        button_row = QHBoxLayout()
        self.ack_button = QPushButton("Acknowledge", container)
        self.ack_button.clicked.connect(self._acknowledge)
        button_row.addWidget(self.ack_button)

        self.more_button = QPushButton("Details", container)
        self.more_button.clicked.connect(self._open_details)
        button_row.addWidget(self.more_button)

        self.mute_button = QPushButton("Mute 30m", container)
        button_row.addWidget(self.mute_button)

        self.sound_button = QPushButton("🔊 Sound ON", container)
        button_row.addWidget(self.sound_button)

        layout.addLayout(button_row)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(container)

        QWidget.setTabOrder(self.ack_button, self.more_button)
        QWidget.setTabOrder(self.more_button, self.mute_button)
        QWidget.setTabOrder(self.mute_button, self.sound_button)

    def _bind_payload(self) -> None:
        headline = self.payload.get("headline") or self.payload.get("event")
        if headline:
            self.headline.setText(headline)
        hazards = self.payload.get("hazards", "Details unavailable")
        self.details.setText(str(hazards))

    def _acknowledge(self) -> None:
        alert_center().acknowledge(self.payload)
        self.close()

    def _open_details(self) -> None:
        ui_factories.open_alert_details(self.payload)

    def mousePressEvent(self, event) -> None:  # noqa: D401
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: D401
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: D401
        self._drag_pos = None
        super().mouseReleaseEvent(event)


def show_window(payload: dict | None = None) -> AlertToast:
    toast = AlertToast(payload or {})
    toast.show()
    return toast


__all__ = ["AlertToast", "show_window"]
