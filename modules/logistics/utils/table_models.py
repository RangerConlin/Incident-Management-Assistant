"""Qt table models for logistics data."""
from __future__ import annotations

from dataclasses import fields
from typing import Any, Iterable

from PySide6 import QtCore

from ..models.dto import Aircraft, Equipment, Personnel, Vehicle


class BaseTableModel(QtCore.QAbstractTableModel):
    """Simple table model backed by a list of dataclasses."""

    def __init__(self, items: list[Any], columns: list[tuple[str, str]], parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._items = items
        self._columns = columns  # list of (header, attribute)

    # Basic model API --------------------------------------------------
    def rowCount(self, parent: QtCore.QModelIndex | None = None) -> int:  # type: ignore[override]
        return len(self._items)

    def columnCount(self, parent: QtCore.QModelIndex | None = None) -> int:  # type: ignore[override]
        return len(self._columns)

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.ItemDataRole.DisplayRole) -> Any:  # type: ignore[override]
        if not index.isValid():
            return None
        item = self._items[index.row()]
        attr = self._columns[index.column()][1]
        value = getattr(item, attr)
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            return str(value)
        return None

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = QtCore.Qt.ItemDataRole.DisplayRole):  # type: ignore[override]
        if orientation == QtCore.Qt.Orientation.Horizontal and role == QtCore.Qt.ItemDataRole.DisplayRole:
            return self._columns[section][0]
        return None

    def set_items(self, items: list[Any]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def item_at(self, row: int) -> Any:
        return self._items[row]


class PersonnelTableModel(BaseTableModel):
    def __init__(self, items: list[Personnel]) -> None:
        columns = [
            ("Role", "role"),
            ("Team", "team_id"),
            ("Phone", "phone"),
            ("Callsign", "callsign"),
            ("Check-In Status", "checkin_status"),
            ("Status", "status"),
        ]
        super().__init__(items, columns)


class EquipmentTableModel(BaseTableModel):
    def __init__(self, items: list[Equipment]) -> None:
        columns = [
            ("Name", "name"),
            ("Type", "type"),
            ("Serial", "serial"),
            ("Team", "assigned_team_id"),
            ("Status", "status"),
        ]
        super().__init__(items, columns)


class VehiclesTableModel(BaseTableModel):
    def __init__(self, items: list[Vehicle]) -> None:
        columns = [
            ("Name", "name"),
            ("Type", "type"),
            ("Callsign", "callsign"),
            ("Team", "assigned_team_id"),
            ("Status", "status"),
        ]
        super().__init__(items, columns)


class AircraftTableModel(BaseTableModel):
    def __init__(self, items: list[Aircraft]) -> None:
        columns = [
            ("Tail", "tail"),
            ("Type", "type"),
            ("Callsign", "callsign"),
            ("Team", "assigned_team_id"),
            ("Status", "status"),
        ]
        super().__init__(items, columns)
