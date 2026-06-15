from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QStatusBar, QWidget, QVBoxLayout

from ..services import CommsLogService
from .quick_entry import QuickEntryWidget
from utils.api_client import api_client


class QuickEntryPanel(QWidget):
    """Dockable panel hosting only the quick entry form."""

    def __init__(self, service: CommsLogService, parent=None,
                 *, incident_id: Optional[str] = None):
        super().__init__(parent)
        self.service = service
        self._incident_id = incident_id
        self._build_ui()
        self._load_data()

    def _build_ui(self) -> None:
        self.setObjectName("communicationsQuickEntry")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.quick_entry = QuickEntryWidget(self)
        self.quick_entry.submitted.connect(self._on_submitted)
        layout.addWidget(self.quick_entry)
        self._status_bar = QStatusBar(self)
        self._status_bar.setStyleSheet("font-size:11px;")
        layout.addWidget(self._status_bar)

    def _load_data(self) -> None:
        channels = self.service.list_channels()
        self.quick_entry.set_channels(channels)

        if self._incident_id:
            try:
                teams = api_client.get(
                    f"/api/incidents/{self._incident_id}/operations/teams"
                ) or []
            except Exception:
                teams = []
            self.quick_entry.populate_teams(teams)

    def _on_submitted(self, payload: dict) -> None:
        from PySide6.QtWidgets import QMessageBox
        try:
            self.service.create_entry(payload)
            self._status_bar.showMessage("Entry saved", 2000)
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed", str(exc))

    def sizeHint(self) -> QSize:
        return QSize(700, 300)

    def minimumSizeHint(self) -> QSize:
        return QSize(520, 240)


__all__ = ["QuickEntryPanel"]
