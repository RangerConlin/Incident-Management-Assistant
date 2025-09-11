"""Aircraft table panel."""

from __future__ import annotations

try:  # pragma: no cover
    from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableView, QPushButton
except Exception:  # pragma: no cover
    QWidget = QVBoxLayout = QTableView = QPushButton = object  # type: ignore

from ..bridges import logistics_bridge as bridge
from ..utils.table_models import BaseTableModel


class AircraftPanel(QWidget):  # pragma: no cover
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.view = QTableView()
        layout.addWidget(self.view)
        btn = QPushButton("Refresh")
        btn.clicked.connect(self.refresh)  # type: ignore[attr-defined]
        layout.addWidget(btn)
        self.refresh()

    def refresh(self):
        data = bridge.list_aircraft()
        self.view.setModel(BaseTableModel(data))
