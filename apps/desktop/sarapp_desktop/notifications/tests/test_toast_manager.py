from __future__ import annotations

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from notifications.widgets.toast_manager import ToastManager, _ToastItem


def test_toast_uses_safe_theme_fallback_for_unknown_severity() -> None:
    app = QApplication.instance() or QApplication([])
    item = _ToastItem(
        {
            "title": "Legacy notification",
            "message": "Unknown severity must not crash the UI.",
            "severity": "info",
            "category": "operations",
        }
    )
    assert item.objectName() == "ToastItem"
    item.deleteLater()
    app.processEvents()


def test_enqueue_reshows_manager_after_empty_state() -> None:
    app = QApplication.instance() or QApplication([])
    parent = QApplication.activeWindow()
    if parent is None:
        from PySide6.QtWidgets import QWidget

        parent = QWidget()
        parent.resize(1000, 700)
        parent.show()
    manager = ToastManager(parent=parent)
    manager.reflow()
    assert not manager.isVisible()

    manager.enqueue({
        "id": "visibility-test",
        "title": "Visible toast",
        "message": "The manager must show itself after being empty.",
        "severity": "routine",
        "category": "operations",
        "toast_mode": "sticky",
    })
    app.processEvents()
    assert manager.isVisible()
    assert manager.width() == 420
    assert parent.height() - manager.geometry().bottom() - 1 == 18
    toast = next(
        manager._layout.itemAt(index).widget()
        for index in range(manager._layout.count())
        if isinstance(manager._layout.itemAt(index).widget(), _ToastItem)
    )
    assert toast.minimumHeight() == 120
    manager.deleteLater()
    parent.deleteLater()
    app.processEvents()


def test_clicking_toast_emits_notification_id() -> None:
    app = QApplication.instance() or QApplication([])
    from PySide6.QtWidgets import QWidget

    parent = QWidget()
    parent.resize(1000, 700)
    parent.show()
    manager = ToastManager(parent=parent)
    clicked: list[str] = []
    manager.toastClicked.connect(clicked.append)
    manager.enqueue({
        "id": "click-test",
        "title": "Clickable toast",
        "message": "Open the notification center.",
        "severity": "routine",
        "category": "operations",
        "toast_mode": "sticky",
    })
    toast = next(
        manager._layout.itemAt(index).widget()
        for index in range(manager._layout.count())
        if isinstance(manager._layout.itemAt(index).widget(), _ToastItem)
    )
    QTest.mouseClick(toast, Qt.LeftButton)
    app.processEvents()
    assert clicked == ["click-test"]
    manager.deleteLater()
    parent.deleteLater()
    app.processEvents()
