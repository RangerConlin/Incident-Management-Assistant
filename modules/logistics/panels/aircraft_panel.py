"""Aircraft management panel."""
from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ..bridges import logistics_bridge
from ..models.dto import Aircraft
from ..utils import table_models, widgets
from .dialogs.aircraft_edit_dialog import AircraftEditDialog


class AircraftPanel(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.toolbar = widgets.Toolbar(self)
        self.toolbar.add_action("Add", self.add_item, "Insert")
        self.toolbar.add_action("Edit", self.edit_item, "Return")
        self.toolbar.add_action("Delete", self.delete_item, "Del")
        self.toolbar.add_action("Refresh", self.refresh, "F5")

        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search")
        self.table = QtWidgets.QTableView()
        self.model = table_models.AircraftTableModel([])
        self.proxy = QtCore.QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.proxy.setFilterKeyColumn(-1)
        self.table.setModel(self.proxy)
        self.table.doubleClicked.connect(lambda _: self.edit_item())
        self.search.textChanged.connect(self.proxy.setFilterFixedString)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.search)
        layout.addWidget(self.table)
        self.refresh()

    def refresh(self) -> None:
        items = logistics_bridge.list_aircraft()
        self.model.set_items(items)

    def _selected(self) -> Aircraft | None:
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        source_index = self.proxy.mapToSource(idx)
        return self.model.item_at(source_index.row())

    def add_item(self) -> None:
        dlg = AircraftEditDialog(self)
        item = dlg.get_aircraft()
        if item:
            logistics_bridge.create_or_update_aircraft(item)
            self.refresh()

    def edit_item(self) -> None:
        item = self._selected()
        if not item:
            return
        dlg = AircraftEditDialog(self, item)
        updated = dlg.get_aircraft()
        if updated:
            logistics_bridge.create_or_update_aircraft(updated)
            self.refresh()

    def delete_item(self) -> None:
        item = self._selected()
        if not item:
            return
        if QtWidgets.QMessageBox.question(self, "Confirm", "Delete selected aircraft?") == QtWidgets.QMessageBox.Yes:
            logistics_bridge.delete_aircraft(item.id)  # type: ignore[arg-type]
            self.refresh()
