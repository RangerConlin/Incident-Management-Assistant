from __future__ import annotations

from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from utils.state import AppState


class _MessagesStub(QWidget):
    """Placeholder for the planned chat integration."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel(
            "Direct messages will appear here once chat is wired into the "
            "notification center.\n\nFor now, use Communications → Chat Messaging."
        )
        label.setWordWrap(True)
        label.setStyleSheet("color: palette(mid); padding: 24px;")
        layout.addWidget(label)
        layout.addStretch(1)


class NotificationCenterPanel(QWidget):
    """Unified hub for activity notifications, pending approvals, and messages."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self._build_activity_tab()
        self._build_approvals_tab()
        self._build_messages_tab()

    def _build_activity_tab(self) -> None:
        from notifications.panels.notifications_panel import get_notifications_panel
        panel = get_notifications_panel(parent=self)
        self.tabs.addTab(panel, "Activity")

    def _build_approvals_tab(self) -> None:
        from modules.approvals.panels.approval_inbox_panel import ApprovalInboxPanel
        incident_id = AppState.get_active_incident()
        personnel_id = str(AppState.get_active_user_id() or "")
        panel = ApprovalInboxPanel(incident_id=incident_id, personnel_id=personnel_id, parent=self)
        panel.load()
        self._approvals_panel = panel
        self.tabs.addTab(panel, "Approvals")

    def _build_messages_tab(self) -> None:
        self.tabs.addTab(_MessagesStub(self), "Messages")

    @property
    def approvals_panel(self):
        return getattr(self, "_approvals_panel", None)

    def jump_to_tab(self, name: str) -> None:
        """Switch to a tab by label: 'activity', 'approvals', or 'messages'."""
        target = name.strip().lower()
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i).strip().lower() == target:
                self.tabs.setCurrentIndex(i)
                return


def get_notification_center_panel(parent: QWidget | None = None) -> NotificationCenterPanel:
    return NotificationCenterPanel(parent)
