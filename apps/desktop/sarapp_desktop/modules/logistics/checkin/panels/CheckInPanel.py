"""QtWidgets implementation of the Logistics ICS-211 panel."""
from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from ..services import CheckInService
from ..widgets import ICS211CheckInWindow


class CheckInPanel(QWidget):
    """Container that embeds the full ICS-211 workbench in a dock/widget."""

    def __init__(
        self,
        parent: QWidget | None = None,
        checkin_service: CheckInService | None = None,
        *,
        auto_refresh: bool = True,
        organization_names: list[str] | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.window = ICS211CheckInWindow(
            self,
            checkin_service=checkin_service,
            auto_refresh=auto_refresh,
            organization_names=organization_names,
        )
        layout.addWidget(self.window)
