from __future__ import annotations

from PySide6 import QtWidgets

from modules.approvals.models import ApprovalStatus

_BADGE_STYLES: dict[ApprovalStatus, tuple[str, str]] = {
    "not_started": ("Not Started", "color: #888888;"),
    "pending": ("Pending", "color: #E6A817; font-weight: bold;"),
    "approved": ("Approved", "color: #3D9970; font-weight: bold;"),
    "rejected": ("Rejected", "color: #CC0000; font-weight: bold;"),
}

_AWAITING_STYLE = "color: #E65400; font-weight: bold;"


class ApprovalBadge(QtWidgets.QLabel):
    """Small inline status chip for list rows and nav items."""

    def set_status(self, status: ApprovalStatus, awaiting_me: bool = False) -> None:
        if awaiting_me and status == "pending":
            self.setText("Awaiting You")
            self.setStyleSheet(_AWAITING_STYLE)
        else:
            text, style = _BADGE_STYLES.get(status, ("Unknown", ""))
            self.setText(text)
            self.setStyleSheet(style)
