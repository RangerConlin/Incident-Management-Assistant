from __future__ import annotations

from datetime import datetime
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
from utils.styles import notification_colors, subscribe_theme


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
        severity_colors, category_colors = notification_colors()
        severity_style = severity_colors.get(severity, severity_colors["routine"])
        category_style = category_colors.get(category, category_colors["system"])
        accent = severity_style["accent"]
        bg = severity_style["background"]
        cat_text = category_style["label"]
        cat_color = category_style["accent"]

        self._apply_frame_style(accent, bg)
        subscribe_theme(self, lambda _name: self._refresh_theme(payload))

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
        self.setStyleSheet(
            f"QFrame {{ background: {bg}; border-left: 3px solid {accent}; "
            f"border-radius: 4px; margin: 2px 0; }}"
        )

    def _refresh_theme(self, payload: dict[str, Any]) -> None:
        severity_colors, _ = notification_colors()
        style = severity_colors.get(str(payload.get("severity") or "routine"), severity_colors["routine"])
        self._apply_frame_style(style["accent"], style["background"])

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
        subscribe_theme(self, lambda _name: self.reload())
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
        entries = get_notification_entries(self.notifier)
        entries = entries[:100]

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
        mark_notification_read(notification_id, self.notifier)
        self.reload()

    def _on_mark_all_read(self) -> None:
        for row in self._server_entries():
            if not row.get("read") and not row.get("requires_acknowledgement"):
                self._mark_server(str(row["id"]), acknowledge=False, reload=False)
        self.notifier.mark_all_read()
        self.reload()

    def _server_entries(self) -> list[dict[str, Any]]:
        return _server_notification_entries()

    def _mark_server(self, notification_id: str, *, acknowledge: bool, reload: bool = True) -> None:
        _mark_server_notification(notification_id, acknowledge=acknowledge)
        if reload:
            self.reload()


def get_notification_entries(notifier=None) -> list[dict[str, Any]]:
    """Return the combined server and local notification feed, newest first."""
    notifier = notifier or get_notifier()
    entries = _server_notification_entries()
    local_ids = {str(row.get("source_id") or "") for row in entries}
    entries.extend(
        row for row in notifier.recent(limit=100)
        if str(row.get("entity_id") or "") not in local_ids
    )
    entries.sort(key=lambda row: int(row.get("ts") or 0), reverse=True)
    return entries


def mark_notification_read(notification_id: str, notifier=None) -> None:
    """Mark either a local or server-backed notification as read."""
    notifier = notifier or get_notifier()
    if notification_id.startswith("server:"):
        _mark_server_notification(
            notification_id,
            acknowledge=notification_id.endswith(":ack"),
        )
    else:
        notifier.mark_read(notification_id)


def _server_notification_entries() -> list[dict[str, Any]]:
    from utils.api_client import api_client
    from utils.state import AppState

    incident_id = AppState.get_active_incident()
    raw_person = AppState.get_active_user_id()
    if not incident_id or not raw_person or not str(raw_person).isdigit():
        return []
    try:
        rows = api_client.get(
            f"/api/incidents/{incident_id}/notifications",
            params={"person_record": int(raw_person)},
        ) or []
    except Exception:
        return []
    result: list[dict[str, Any]] = []
    for row in rows:
        created = str(row.get("created_at") or "")
        try:
            ts = int(datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp())
        except (TypeError, ValueError):
            ts = 0
        result.append({
            "id": f"server:{row.get('notification_id')}:{'ack' if row.get('requires_acknowledgement') else 'dismiss'}",
            "server_id": row.get("notification_id"),
            "title": row.get("title", ""),
            "message": row.get("message", ""),
            "severity": row.get("severity", "routine"),
            "category": row.get("category", "operations"),
            "source": row.get("source_label") or row.get("source_type") or "System",
            "source_id": row.get("source_id"),
            "requires_acknowledgement": bool(row.get("requires_acknowledgement")),
            "read": bool(row.get("read")),
            "ts": ts,
        })
    return result


def _mark_server_notification(notification_id: str, *, acknowledge: bool) -> None:
    from utils.api_client import api_client
    from utils.state import AppState

    incident_id = AppState.get_active_incident()
    raw_person = AppState.get_active_user_id()
    if not incident_id or not raw_person or not str(raw_person).isdigit():
        return
    record_id = notification_id.removeprefix("server:").split(":", 1)[0]
    action = "acknowledge" if acknowledge else "dismiss"
    try:
        api_client.post(
            f"/api/incidents/{incident_id}/notifications/{record_id}/{action}",
            json={"person_record": int(raw_person)},
        )
    except Exception:
        return


def get_notifications_panel(parent: QWidget | None = None) -> NotificationsPanel:
    return NotificationsPanel(parent)
