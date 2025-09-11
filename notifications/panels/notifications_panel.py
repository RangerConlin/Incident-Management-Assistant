from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem

from notifications.services import get_notifier
from utils.app_signals import app_signals


class NotificationsPanel(QWidget):
    """Panel showing the notification activity feed."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.notifier = get_notifier()
        layout = QVBoxLayout(self)
        try:
            layout.setContentsMargins(0, 0, 0, 0)
        except Exception:
            pass
        self.list = QListWidget()
        layout.addWidget(self.list)

        self.notifier.notificationCreated.connect(lambda *_: self.reload())
        app_signals.incidentChanged.connect(lambda *_: self.reload())
        self.reload()

    def reload(self) -> None:
        entries = self.notifier.recent()
        self.list.clear()
        for entry in entries:
            text = entry.get("message", str(entry)) if isinstance(entry, dict) else str(entry)
            QListWidgetItem(text, self.list)
        self.notifier.clear_badge()


def get_notifications_panel(parent: QWidget | None = None) -> NotificationsPanel:
    return NotificationsPanel(parent)
