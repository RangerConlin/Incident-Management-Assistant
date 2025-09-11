"""Main Qt widget for Logistics features.

The panel exposes four tabs – Personnel, Equipment, Vehicles and Aircraft –
which each display a simple table view backed by the bridge functions.  The UI
is deliberately lightweight so the module remains functional in environments
without full Qt capabilities (e.g. during unit testing).
"""

from __future__ import annotations

try:  # pragma: no cover - UI not exercised in tests
    from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget
except Exception:  # pragma: no cover
    QTabWidget = QVBoxLayout = QWidget = object  # type: ignore

from ..bridges import logistics_bridge as bridge
from ..utils.table_models import BaseTableModel, PersonnelTableModel
from ..models.dto import Personnel, Equipment, Vehicle, Aircraft


class _SimpleTable(QWidget):  # pragma: no cover - trivial wrapper around Qt
    def __init__(self, loader, model_cls=BaseTableModel):
        super().__init__()
        from PySide6.QtWidgets import QVBoxLayout, QTableView, QPushButton

        layout = QVBoxLayout(self)
        self.view = QTableView()
        layout.addWidget(self.view)
        btn = QPushButton("Refresh")
        btn.clicked.connect(self.refresh)  # type: ignore[attr-defined]
        layout.addWidget(btn)
        self._loader = loader
        self._model_cls = model_cls
        self.refresh()

    def refresh(self):  # pragma: no cover - trivial
        data = self._loader()
        self.view.setModel(self._model_cls(data))


class LogisticsHomePanel(QWidget):  # pragma: no cover - UI heavy
    """Tabbed panel aggregating all logistics tables."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        tabs.addTab(_SimpleTable(bridge.list_personnel, PersonnelTableModel), "Personnel")
        tabs.addTab(_SimpleTable(bridge.list_equipment), "Equipment")
        tabs.addTab(_SimpleTable(bridge.list_vehicles), "Vehicles")
        tabs.addTab(_SimpleTable(bridge.list_aircraft), "Aircraft")
