from __future__ import annotations

from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from notifications.panels.notifications_panel import (
    get_notification_entries,
    mark_notification_read,
)
from notifications.services import get_notifier


class NotificationDrawer(QFrame):
    """Compact unread-notification popup opened from the status bar bell."""

    openCenterRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setObjectName("NotificationDrawer")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFixedWidth(420)
        self.setMaximumHeight(560)
        self.setStyleSheet(
            "QFrame#NotificationDrawer { background: palette(window); "
            "border: 1px solid palette(mid); border-radius: 8px; }"
        )

        self._stack = QStackedWidget(self)
        self._list_page = QWidget(self)
        self._detail_page = QWidget(self)
        self._stack.addWidget(self._list_page)
        self._stack.addWidget(self._detail_page)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._stack)

        self._build_list_page()
        self._build_detail_page()

        notifier = get_notifier()
        notifier.notificationCreated.connect(lambda _payload: self.reload())
        notifier.notificationUpdated.connect(lambda _payload: self.reload())

    def _build_list_page(self) -> None:
        layout = QVBoxLayout(self._list_page)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(10)

        heading = QLabel("Unread Notifications")
        heading.setStyleSheet("font-size: 15px; font-weight: 700;")
        layout.addWidget(heading)

        self._empty = QLabel("You're all caught up.")
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setStyleSheet("color: palette(mid); padding: 28px;")
        layout.addWidget(self._empty)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._items = QWidget()
        self._items_layout = QVBoxLayout(self._items)
        self._items_layout.setContentsMargins(0, 0, 0, 0)
        self._items_layout.setSpacing(6)
        self._items_layout.addStretch(1)
        self._scroll.setWidget(self._items)
        layout.addWidget(self._scroll, 1)

        center = QPushButton("Open Notification Center")
        center.clicked.connect(self.openCenterRequested.emit)
        layout.addWidget(center)

    def _build_detail_page(self) -> None:
        layout = QVBoxLayout(self._detail_page)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(10)

        back = QPushButton("← Back to unread")
        back.clicked.connect(self.show_list)
        layout.addWidget(back, 0, Qt.AlignLeft)

        self._detail_title = QLabel()
        self._detail_title.setWordWrap(True)
        self._detail_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        layout.addWidget(self._detail_title)

        self._detail_meta = QLabel()
        self._detail_meta.setWordWrap(True)
        self._detail_meta.setStyleSheet("color: palette(mid);")
        layout.addWidget(self._detail_meta)

        self._detail_message = QLabel()
        self._detail_message.setWordWrap(True)
        self._detail_message.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self._detail_message, 1)

        center = QPushButton("Open Notification Center")
        center.clicked.connect(self.openCenterRequested.emit)
        layout.addWidget(center)

    def reload(self) -> None:
        while self._items_layout.count() > 1:
            item = self._items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        unread = [row for row in get_notification_entries() if not row.get("read")]
        self._empty.setVisible(not unread)
        self._scroll.setVisible(bool(unread))
        for payload in unread:
            button = QPushButton(self._button_text(payload))
            button.setCursor(Qt.PointingHandCursor)
            button.setMinimumHeight(54)
            button.setStyleSheet("text-align: left; padding: 8px 10px;")
            button.clicked.connect(lambda _checked=False, row=payload: self.open_notification(row))
            self._items_layout.insertWidget(self._items_layout.count() - 1, button)
        self.adjustSize()

    @staticmethod
    def _button_text(payload: dict[str, Any]) -> str:
        title = str(payload.get("title") or "Notification")
        message = str(payload.get("message") or "").replace("\n", " ")
        if len(message) > 90:
            message = f"{message[:87]}…"
        return f"{title}\n{message}" if message else title

    def open_notification(self, payload: dict[str, Any]) -> None:
        mark_notification_read(str(payload.get("id") or ""))
        self._detail_title.setText(str(payload.get("title") or "Notification"))
        source = str(payload.get("source") or "System")
        timestamp = ""
        try:
            timestamp = datetime.fromtimestamp(int(payload.get("ts") or 0)).strftime("%b %d, %Y %I:%M %p")
        except (TypeError, ValueError, OSError):
            pass
        self._detail_meta.setText(" • ".join(part for part in (source, timestamp) if part))
        self._detail_message.setText(str(payload.get("message") or ""))
        self._stack.setCurrentWidget(self._detail_page)

    def show_list(self) -> None:
        self.reload()
        self._stack.setCurrentWidget(self._list_page)

