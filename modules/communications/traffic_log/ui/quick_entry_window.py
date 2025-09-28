from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QStatusBar, QWidget, QVBoxLayout

from ..services import CommsLogService
from .quick_entry import QuickEntryWidget


class QuickEntryPanel(QWidget):
    """Dockable panel hosting only the quick entry form."""

    def __init__(self, service: CommsLogService, parent=None):
        super().__init__(parent)
        self.service = service
        self._build_ui()

    def _build_ui(self) -> None:
        self.setObjectName("communicationsQuickEntry")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self.quick_entry = QuickEntryWidget(self)
        self.quick_entry.submitted.connect(self._on_submitted)
        layout.addWidget(self.quick_entry)
        # Optional local status bar when used standalone
        self._status_bar = QStatusBar(self)
        layout.addWidget(self._status_bar)

    def _on_submitted(self, payload: dict) -> None:
        try:
            self.service.create_entry(payload)
        finally:
            self._status_bar.showMessage("Entry added", 2000)

__all__ = ["QuickEntryPanel"]

    # Preferred initial size similar to previous standalone window
    def sizeHint(self) -> QSize:  # type: ignore[override]
        return QSize(700, 300)

    def minimumSizeHint(self) -> QSize:  # type: ignore[override]
        return QSize(520, 240)
