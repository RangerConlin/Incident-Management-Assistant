"""Smoke tests for the notifications settings page."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFrame, QScrollArea

from ui.settings.pages.notifications_page import NotificationsPage


class _SettingsBridge:
    def getSetting(self, _key: str):
        return None

    def setSetting(self, _key: str, _value) -> None:
        return None


def test_notifications_page_constructs_with_frameless_scroll_area() -> None:
    app = QApplication.instance() or QApplication([])
    page = NotificationsPage(_SettingsBridge())

    scroll = page.findChild(QScrollArea)

    assert scroll is not None
    assert scroll.frameShape() == QFrame.Shape.NoFrame
    page.deleteLater()
    app.processEvents()
