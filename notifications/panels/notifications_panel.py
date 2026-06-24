from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QDateTime, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from notifications.services import get_notifier
from utils.app_signals import app_signals

_SEVERITY_ACCENT = {
    "informational": "#444444",
    "routine":       "#888888",
    "priority":      "#D9A938",
    "emergency":     "#D93838",
}
_SEVERITY_BG = {
    "informational": "#1e1e1e",
    "routine":       "#282828",
    "priority":      "#3a2e1a",
    "emergency":     "#3a1a1a",
}
_CATEGORY_LABEL = {
    "operations":     ("OPS",   "#3879D9"),
    "communications": ("COMMS", "#38A8D9"),
    "safety":         ("SAFETY","#D9A938"),
    "logistics":      ("LOG",   "#8A38D9"),
    "planning":       ("PLAN",  "#38D978"),
    "administrative": ("ADMIN", "#888888"),
    "system":         ("SYS",   "#888888"),
}


class _NotificationRow(QFrame):
    clicked = Signal(str)  # notification id

    def __init__(self, payload: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._id = str(payload.get("id") or "")
        self._read = bool(payload.get("read", False))
        self.setCursor(Qt.PointingHandCursor)

        severity = str(payload.get("severity") or "routine")
        category = str(payload.get("category") or "operations")
        accent = _SEVERITY_ACCENT.get(severity, _SEVERITY_ACCENT["routine"])
        bg = _SEVERITY_BG.get(severity, _SEVERITY_BG["routine"])
        cat_text, cat_color = _CATEGORY_LABEL.get(category, ("", "#888888"))

        self._apply_frame_style(accent, bg)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(2)

        header = QHBoxLayout()
        header.setSpacing(8)

        if not self._read:
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {accent}; font-size: 10px;")
            dot.setFixedWidth(12)
            header.addWidget(dot, 0)

        if cat_text:
            cat_lbl = QLabel(cat_text)
            cat_lbl.setStyleSheet(
                f"color: {cat_color}; font-size: 10px; font-weight: 700;"
                " padding: 1px 4px; border-radius: 3px;"
                f" border: 1px solid {cat_color};"
            )
            header.addWidget(cat_lbl, 0)

        title_lbl = QLabel(str(payload.get("title") or ""))
        title_lbl.setStyleSheet("font-weight: 600;" if not self._read else "font-weight: 400; color: palette(mid);")
        header.addWidget(title_lbl, 1)

        source = str(payload.get("source") or "")
        if source:
            source_lbl = QLabel(source)
            source_lbl.setStyleSheet("color: palette(mid); font-size: 11px;")
            header.addWidget(source_lbl)

        ts = payload.get("ts")
        if ts:
            try:
                dt = QDateTime.fromSecsSinceEpoch(int(ts))
                time_str = dt.toString("hh:mm")
            except Exception:
                time_str = ""
            if time_str:
                time_lbl = QLabel(time_str)
                time_lbl.setStyleSheet("color: palette(mid); font-size: 11px;")
                header.addWidget(time_lbl)

        layout.addLayout(header)

        message = str(payload.get("message") or "")
        if message:
            msg_lbl = QLabel(message)
            msg_lbl.setWordWrap(True)
            msg_lbl.setStyleSheet("color: palette(window-text);")
            layout.addWidget(msg_lbl)

    def _apply_frame_style(self, accent: str, bg: str) -> None:
        opacity = "22" if not self._read else "0a"
        self.setStyleSheet(
            f"QFrame {{ background: {bg}{opacity}; border-left: 3px solid {accent}; "
            f"border-radius: 4px; margin: 2px 0; }}"
        )

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if self._id:
            self.clicked.emit(self._id)
        super().mousePressEvent(event)


class NotificationsPanel(QWidget):
    """Dockable notification history feed."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.notifier = get_notifier()
        self._build_ui()

        self.notifier.notificationCreated.connect(lambda _: self.reload())
        self.notifier.notificationUpdated.connect(lambda _: self.reload())
        app_signals.incidentChanged.connect(lambda _: self.reload())
        self.reload()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header bar
        header = QWidget()
        header.setObjectName("panelHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 8, 8)
        header_layout.setSpacing(8)

        title = QLabel("Notifications")
        title.setStyleSheet("font-weight: 600; font-size: 13px;")
        header_layout.addWidget(title, 1)

        mark_all_btn = QPushButton("Mark All Read")
        mark_all_btn.setFixedHeight(26)
        mark_all_btn.clicked.connect(self._on_mark_all_read)
        header_layout.addWidget(mark_all_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedHeight(26)
        refresh_btn.clicked.connect(self.reload)
        header_layout.addWidget(refresh_btn)

        root.addWidget(header)

        # Scroll area for rows
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.NoFrame)

        self._feed_container = QWidget()
        self._feed_layout = QVBoxLayout(self._feed_container)
        self._feed_layout.setContentsMargins(8, 8, 8, 8)
        self._feed_layout.setSpacing(4)
        self._feed_layout.addStretch(1)

        self._scroll.setWidget(self._feed_container)
        root.addWidget(self._scroll)

        self._empty_label = QLabel("No notifications yet.")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet("color: palette(mid); padding: 24px;")
        self._empty_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root.addWidget(self._empty_label)

    def reload(self) -> None:
        entries = self.notifier.recent(limit=100)

        # Clear existing rows (all widgets except the stretch)
        while self._feed_layout.count() > 1:
            item = self._feed_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        if not entries:
            self._scroll.hide()
            self._empty_label.show()
            return

        self._empty_label.hide()
        self._scroll.show()

        for payload in entries:
            row = _NotificationRow(payload)
            row.clicked.connect(self._on_row_clicked)
            self._feed_layout.insertWidget(self._feed_layout.count() - 1, row)

    def _on_row_clicked(self, notification_id: str) -> None:
        self.notifier.mark_read(notification_id)

    def _on_mark_all_read(self) -> None:
        self.notifier.mark_all_read()


def get_notifications_panel(parent: QWidget | None = None) -> NotificationsPanel:
    return NotificationsPanel(parent)
