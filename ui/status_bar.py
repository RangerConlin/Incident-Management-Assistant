from __future__ import annotations

from PySide6 import QtCore, QtWidgets

try:
    from core.networking.server_info import ConnectionState
    _HAS_CONNECTION_STATE = True
except Exception:
    _HAS_CONNECTION_STATE = False

_CONNECTION_STYLES = {
    "CONNECTED_LAN":   ("● Connected (LAN)",   "color: #3D9970;"),
    "CONNECTED_CLOUD": ("● Connected (Cloud)",  "color: #3D9970;"),
    "CONNECTING":      ("● Connecting…",        "color: #E6A817;"),
    "DISCOVERING":     ("● Discovering…",       "color: #E6A817;"),
    "DISCONNECTED":    ("● Disconnected",       "color: #CC0000;"),
    "OFFLINE":         ("● Offline Mode",       "color: #888888;"),
}

_POLL_INTERVAL_MS = 30_000  # 30 seconds


class AppStatusBar(QtWidgets.QStatusBar):
    """
    Bottom status bar:
      Left   — connection status
      Right  — notification badge, pending approvals, unread messages (all clickable)
    """

    approval_indicator_clicked = QtCore.Signal()
    messages_indicator_clicked = QtCore.Signal()
    notifications_indicator_clicked = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizeGripEnabled(False)
        self.setFixedHeight(24)

        # Connection status — left, permanent
        self._conn_label = QtWidgets.QLabel("● —")
        self._conn_label.setStyleSheet("color: #888888; padding: 0 8px;")
        self.addWidget(self._conn_label)

        # Spacer to push right-side items to the right
        spacer = QtWidgets.QWidget()
        spacer.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred
        )
        self.addWidget(spacer)

        # Notification badge — permanent right-side, driven by Notifier signal (not polled)
        self._notifications_btn = QtWidgets.QPushButton("\U0001F514 0")
        self._notifications_btn.setFlat(True)
        self._notifications_btn.setStyleSheet("color: #888888; padding: 0 8px; border: none;")
        self._notifications_btn.setToolTip("Notifications")
        self._notifications_btn.clicked.connect(self.notifications_indicator_clicked)
        self.addPermanentWidget(self._notifications_btn)

        # Pending approvals — permanent right-side
        self._approvals_btn = QtWidgets.QPushButton("✔ —")
        self._approvals_btn.setFlat(True)
        self._approvals_btn.setStyleSheet("color: #888888; padding: 0 8px; border: none;")
        self._approvals_btn.setToolTip("Pending approvals")
        self._approvals_btn.clicked.connect(self.approval_indicator_clicked)
        self.addPermanentWidget(self._approvals_btn)

        # Unread messages — permanent right-side
        self._messages_btn = QtWidgets.QPushButton("✉ —")
        self._messages_btn.setFlat(True)
        self._messages_btn.setStyleSheet("color: #888888; padding: 0 8px; border: none;")
        self._messages_btn.setToolTip("Unread messages")
        self._messages_btn.clicked.connect(self.messages_indicator_clicked)
        self.addPermanentWidget(self._messages_btn)

        # Poll timer for approvals and messages counts
        self._poll_timer = QtCore.QTimer(self)
        self._poll_timer.setInterval(_POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_counts)

    # ------------------------------------------------------------------
    # Public API

    def start(self) -> None:
        """Begin polling. Call after the main window is fully initialised."""
        self._poll_counts()
        self._poll_timer.start()

    def stop(self) -> None:
        self._poll_timer.stop()

    # ------------------------------------------------------------------
    # Connection status — driven by ConnectionManager listener

    def on_connection_snapshot(self, snapshot) -> None:
        """Called from any thread; schedules label update on the main thread."""
        QtCore.QTimer.singleShot(0, lambda: self._apply_snapshot(snapshot))

    def _apply_snapshot(self, snapshot) -> None:
        try:
            state_key = snapshot.state.name if hasattr(snapshot.state, "name") else str(snapshot.state)
            text, style = _CONNECTION_STYLES.get(state_key, ("● —", "color: #888888;"))
            self._conn_label.setText(text)
            self._conn_label.setStyleSheet(f"{style} padding: 0 8px;")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Counts polling

    def _poll_counts(self) -> None:
        self._poll_approvals()
        self._poll_messages()

    def _poll_approvals(self) -> None:
        try:
            from utils.state import AppState
            from utils.api_client import api_client
            incident_id = AppState.get_active_incident()
            personnel_id = AppState.get_active_user_id()
            if not incident_id or not personnel_id:
                self._set_approvals(None)
                return

            # Resolve roles for this person
            assignments = api_client.get(
                f"/api/incidents/{incident_id}/org/assignments/by-person/{personnel_id}"
            ) or []
            roles = [a.get("position_title", "") for a in assignments if a.get("position_title")]

            result = api_client.post(
                f"/api/incidents/{incident_id}/approvals/pending",
                json={"roles": roles, "personnel_id": str(personnel_id)},
            ) or []
            self._set_approvals(len(result))
        except Exception:
            self._set_approvals(None)

    def _poll_messages(self) -> None:
        try:
            from utils.state import AppState
            from utils.api_client import api_client
            incident_id = AppState.get_active_incident()
            if not incident_id:
                self._set_messages(None)
                return
            result = api_client.get(
                f"/api/incidents/{incident_id}/comms/unread-count"
            ) or {}
            self._set_messages(int(result.get("count", 0)))
        except Exception:
            self._set_messages(None)

    def set_notifications_count(self, count: int) -> None:
        if count <= 0:
            self._notifications_btn.setText("\U0001F514 0")
            self._notifications_btn.setStyleSheet("color: #888888; padding: 0 8px; border: none;")
        else:
            self._notifications_btn.setText(f"\U0001F514 {count}")
            self._notifications_btn.setStyleSheet("color: #E65400; font-weight: bold; padding: 0 8px; border: none;")
        self._notifications_btn.setToolTip(
            f"{count} unread notification(s)" if count else "No unread notifications"
        )

    def _set_approvals(self, count: int | None) -> None:
        if count is None:
            self._approvals_btn.setText("✔ —")
            self._approvals_btn.setStyleSheet("color: #888888; padding: 0 8px; border: none;")
        elif count == 0:
            self._approvals_btn.setText("✔ 0")
            self._approvals_btn.setStyleSheet("color: #888888; padding: 0 8px; border: none;")
        else:
            self._approvals_btn.setText(f"✔ {count}")
            self._approvals_btn.setStyleSheet("color: #E65400; font-weight: bold; padding: 0 8px; border: none;")
        self._approvals_btn.setToolTip(
            f"{count} pending approval(s)" if count else "No pending approvals"
        )

    def _set_messages(self, count: int | None) -> None:
        if count is None:
            self._messages_btn.setText("✉ —")
            self._messages_btn.setStyleSheet("color: #888888; padding: 0 8px; border: none;")
        elif count == 0:
            self._messages_btn.setText("✉ 0")
            self._messages_btn.setStyleSheet("color: #888888; padding: 0 8px; border: none;")
        else:
            self._messages_btn.setText(f"✉ {count}")
            self._messages_btn.setStyleSheet("color: #E65400; font-weight: bold; padding: 0 8px; border: none;")
        self._messages_btn.setToolTip(
            f"{count} unread message(s)" if count else "No unread messages"
        )
