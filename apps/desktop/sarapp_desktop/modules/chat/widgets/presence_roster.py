"""Right-pane roster of who else is online in this incident, plus a picker
for the current user's own status.

Presence is poll-driven, not event-pushed: going offline is "my last
heartbeat went stale," which only the periodic `GET .../presence` call can
detect (see `PRESENCE_STALE_AFTER_SECONDS` in `chat.py`) — no live event is
ever sent for it. `ChatWindow` owns the poll timer and feeds the same
status map to this panel and to `ChatChannelList`'s DM status dots.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPixmap
from PySide6.QtWidgets import QComboBox, QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from utils.presence import PRESENCE_STATUSES, presence
from utils.styles import get_palette, subscribe_theme

STATUS_LABELS = {"online": "Online", "away": "Away", "unavailable": "Unavailable"}
_STATUS_PALETTE_KEY = {"online": "success", "away": "warning", "unavailable": "danger"}


def status_color_name(status: str) -> str:
    pal = get_palette()
    key = _STATUS_PALETTE_KEY.get(status, "muted")
    return pal.get(key, pal["muted"]).name()


def status_dot_icon(status: str, *, diameter: int = 10) -> QPixmap:
    pixmap = QPixmap(diameter, diameter)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QBrush(QColor(status_color_name(status))))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(0, 0, diameter, diameter)
    painter.end()
    return pixmap


class PresenceRoster(QWidget):
    """Lists other users currently online; double-click starts a DM."""

    userActivated = Signal(str)  # user_id

    def __init__(self, parent=None):
        super().__init__(parent)

        status_label = QLabel("Your status", self)
        status_label.setObjectName("rosterSectionLabel")

        self._status_combo = QComboBox(self)
        for status in PRESENCE_STATUSES:
            self._status_combo.addItem(STATUS_LABELS[status], status)
        self._status_combo.setCurrentIndex(self._status_combo.findData(presence.status))
        self._status_combo.currentIndexChanged.connect(self._on_status_picked)

        online_label = QLabel("Online", self)
        online_label.setObjectName("rosterSectionLabel")

        self._list = QListWidget(self)
        self._list.itemDoubleClicked.connect(self._on_item_activated)

        layout = QVBoxLayout(self)
        layout.addWidget(status_label)
        layout.addWidget(self._status_combo)
        layout.addWidget(online_label)
        layout.addWidget(self._list, 1)

        self._apply_styles()
        subscribe_theme(self, lambda *_: self._apply_styles())
        presence.statusChanged.connect(self._sync_status_combo)

    def _apply_styles(self) -> None:
        pal = get_palette()
        fg_muted = pal.get("fg_muted", pal["muted"]).name()
        self.setStyleSheet(
            "QLabel#rosterSectionLabel {"
            f" color: {fg_muted}; font-size: 10px; font-weight: 700;"
            " letter-spacing: 0.5px; padding-top: 6px;"
            "}"
        )

    def _on_status_picked(self, index: int) -> None:
        status = self._status_combo.itemData(index)
        if status:
            presence.set_status(status)

    def _sync_status_combo(self, status: str) -> None:
        index = self._status_combo.findData(status)
        if index >= 0 and index != self._status_combo.currentIndex():
            self._status_combo.blockSignals(True)
            self._status_combo.setCurrentIndex(index)
            self._status_combo.blockSignals(False)

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        user_id = item.data(Qt.UserRole)
        if user_id:
            self.userActivated.emit(user_id)

    def set_online_users(self, users: list[tuple[str, str, str]]) -> None:
        """Replace the roster. `users` is (user_id, display_name, status) tuples."""
        selected = self._list.currentItem().data(Qt.UserRole) if self._list.currentItem() else None
        self._list.clear()
        for user_id, display_name, status in users:
            item = QListWidgetItem(status_dot_icon(status), display_name)
            item.setData(Qt.UserRole, user_id)
            self._list.addItem(item)
            if user_id == selected:
                self._list.setCurrentItem(item)


__all__ = ["PresenceRoster", "status_color_name", "status_dot_icon"]
