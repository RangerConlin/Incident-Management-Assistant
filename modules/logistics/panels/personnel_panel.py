"""Personnel table panel."""

from __future__ import annotations

try:  # pragma: no cover
    from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableView, QPushButton, QCheckBox
except Exception:  # pragma: no cover
    QWidget = QVBoxLayout = QTableView = QPushButton = QCheckBox = object  # type: ignore

from ..bridges import logistics_bridge as bridge
from ..utils.table_models import PersonnelTableModel
from ..models.dto import CheckInStatus


class PersonnelPanel(QWidget):  # pragma: no cover
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.view = QTableView()
        layout.addWidget(self.view)
        self._show_noshow = QCheckBox("Show NoShow")
        self._show_noshow.toggled.connect(self.refresh)  # type: ignore[attr-defined]
        layout.addWidget(self._show_noshow)
        btn = QPushButton("Refresh")
        btn.clicked.connect(self.refresh)  # type: ignore[attr-defined]
        layout.addWidget(btn)
        self.refresh()

    def refresh(self):
        data = bridge.list_personnel()
        if not self._show_noshow.isChecked():  # type: ignore[attr-defined]
            data = [p for p in data if p.checkin_status != CheckInStatus.NO_SHOW]
        self.view.setModel(PersonnelTableModel(data))
