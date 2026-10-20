from __future__ import annotations

from PySide6 import QtWidgets

from modules.approvals.models import ApprovalStatus
from utils.styles import approval_awaiting_me_color, approval_status_colors, subscribe_theme

_LABELS: dict[ApprovalStatus, str] = {
    "not_started": "Not Started",
    "pending": "Pending",
    "approved": "Approved",
    "rejected": "Rejected",
}


class ApprovalBadge(QtWidgets.QLabel):
    """Small inline status chip for list rows and nav items."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._status: ApprovalStatus = "not_started"
        self._awaiting_me = False
        subscribe_theme(self, lambda *_: self._apply_style())

    def set_status(self, status: ApprovalStatus, awaiting_me: bool = False) -> None:
        self._status = status
        self._awaiting_me = awaiting_me
        self._apply_style()

    def _apply_style(self) -> None:
        if self._awaiting_me and self._status == "pending":
            self.setText("Awaiting You")
            color = approval_awaiting_me_color().name()
            self.setStyleSheet(f"color: {color}; font-weight: bold;")
            return
        colors = approval_status_colors().get(self._status)
        self.setText(_LABELS.get(self._status, "Unknown"))
        if colors:
            self.setStyleSheet(f"color: {colors['bg'].color().name()}; font-weight: bold;")
        else:
            self.setStyleSheet("")
