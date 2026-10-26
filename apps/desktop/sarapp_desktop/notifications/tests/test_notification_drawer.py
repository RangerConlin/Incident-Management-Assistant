from __future__ import annotations

from PySide6.QtWidgets import QApplication, QPushButton

import notifications.widgets.notification_drawer as drawer_module
from notifications.widgets.notification_drawer import NotificationDrawer


def test_drawer_shows_only_unread_and_opens_detail(monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    entries = [
        {"id": "unread-1", "title": "Needs attention", "message": "Review this item", "source": "Test", "ts": 1, "read": False},
        {"id": "read-1", "title": "Already read", "message": "Hidden", "source": "Test", "ts": 1, "read": True},
    ]
    marked: list[str] = []
    monkeypatch.setattr(drawer_module, "get_notification_entries", lambda: entries)
    monkeypatch.setattr(drawer_module, "mark_notification_read", marked.append)

    drawer = NotificationDrawer()
    drawer.show_list()
    buttons = drawer._items.findChildren(QPushButton)
    assert len(buttons) == 1
    assert "Needs attention" in buttons[0].text()

    buttons[0].click()
    app.processEvents()
    assert marked == ["unread-1"]
    assert drawer._stack.currentWidget() is drawer._detail_page
    assert drawer._detail_title.text() == "Needs attention"
    assert drawer._detail_message.text() == "Review this item"
    drawer.deleteLater()
    app.processEvents()


def test_drawer_can_request_full_notification_center(monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(drawer_module, "get_notification_entries", lambda: [])
    drawer = NotificationDrawer()
    requests: list[bool] = []
    drawer.openCenterRequested.connect(lambda: requests.append(True))
    center_buttons = [
        button for button in drawer.findChildren(QPushButton)
        if button.text() == "Open Notification Center"
    ]
    center_buttons[0].click()
    app.processEvents()
    assert requests == [True]
    drawer.deleteLater()
    app.processEvents()
