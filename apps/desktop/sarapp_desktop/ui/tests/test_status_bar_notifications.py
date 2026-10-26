from __future__ import annotations

from PySide6.QtWidgets import QApplication

from ui.status_bar import AppStatusBar


def test_notification_button_emits_indicator_signal() -> None:
    app = QApplication.instance() or QApplication([])
    bar = AppStatusBar()
    clicks: list[bool] = []
    bar.notifications_indicator_clicked.connect(lambda: clicks.append(True))
    bar._notifications_btn.click()
    app.processEvents()
    assert clicks == [True]
    bar.deleteLater()
    app.processEvents()
