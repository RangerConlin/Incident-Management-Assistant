"""Personnel management panel."""
from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ..bridges import logistics_bridge
from ..models.dto import Personnel
from ..utils import table_models, widgets
from .dialogs.personnel_edit_dialog import PersonnelEditDialog


class PersonnelPanel(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.toolbar = widgets.Toolbar(self)
        self.toolbar.add_action("Add", self.add_person, "Insert")
        self.toolbar.add_action("Edit", self.edit_person, "Return")
        self.toolbar.add_action("Delete", self.delete_person, "Del")
        self.toolbar.add_action("Refresh", self.refresh, "F5")

        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search")
        self.table = QtWidgets.QTableView()
        self.model = table_models.PersonnelTableModel([])
        self.proxy = QtCore.QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.proxy.setFilterKeyColumn(-1)
        self.table.setModel(self.proxy)
        self.table.doubleClicked.connect(lambda _: self.edit_person())
        self.search.textChanged.connect(self.proxy.setFilterFixedString)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.search)
        layout.addWidget(self.table)
        self.refresh()

    # Actions -----------------------------------------------------------
    def refresh(self) -> None:
        items = logistics_bridge.list_personnel()
        self.model.set_items(items)

    def _selected_person(self) -> Personnel | None:
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        source_index = self.proxy.mapToSource(idx)
        return self.model.item_at(source_index.row())

    def add_person(self) -> None:
        dlg = PersonnelEditDialog(self)
        person = dlg.get_person()
        if person:
            logistics_bridge.create_or_update_personnel(person)
            self.refresh()

    def edit_person(self) -> None:
        person = self._selected_person()
        if not person:
            return
        dlg = PersonnelEditDialog(self, person)
        updated = dlg.get_person()
        if updated:
            logistics_bridge.create_or_update_personnel(updated)
            self.refresh()

    def delete_person(self) -> None:
        person = self._selected_person()
        if not person:
            return
        if QtWidgets.QMessageBox.question(self, "Confirm", "Delete selected personnel?") == QtWidgets.QMessageBox.Yes:
            logistics_bridge.delete_personnel(person.id)  # type: ignore[arg-type]
            self.refresh()
