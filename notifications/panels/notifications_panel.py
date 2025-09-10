from __future__ import annotations

import os
from typing import Any

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtQuickWidgets import QQuickWidget

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
        self.view = QQuickWidget()
        self.view.setResizeMode(QQuickWidget.SizeRootObjectToView)
        qml_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "qml", "NotificationFeed.qml")
        )
        self.view.setSource(QUrl.fromLocalFile(qml_path))
        layout.addWidget(self.view)

        self.notifier.notificationCreated.connect(lambda *_: self.reload())
        app_signals.incidentChanged.connect(lambda *_: self.reload())
        self.reload()

    def reload(self) -> None:
        entries = self.notifier.recent()
        root = self.view.rootObject()
        if root is not None:
            try:
                root.setEntries(entries)
            except Exception:
                pass
        self.notifier.clear_badge()


def get_notifications_panel(parent: QWidget | None = None) -> NotificationsPanel:
    return NotificationsPanel(parent)
