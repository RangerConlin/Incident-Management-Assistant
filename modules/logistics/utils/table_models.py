"""Qt table models for logistics data.

The models expose rows of dataclass instances to ``QTableView`` widgets.  Only a
very small subset of Qt's model API is implemented to keep the module focused
and lightweight; it is sufficient for unit tests and basic UI rendering.
"""

from __future__ import annotations

from dataclasses import fields
from typing import Iterable, Sequence

from ..models.dto import CheckInStatus

try:  # pragma: no cover - UI components not executed in tests
    from PySide6 import QtCore
except Exception:  # pragma: no cover
    QtCore = object  # type: ignore


class BaseTableModel(QtCore.QAbstractTableModel):  # type: ignore[misc]
    """Generic table model for a list of dataclass instances."""

    def __init__(self, data: Iterable[object]):
        super().__init__()
        self._items = list(data)
        self._fields = [f.name for f in fields(self._items[0])] if self._items else []

    def rowCount(self, parent: QtCore.QModelIndex | None = None) -> int:  # type: ignore[override]
        return len(self._items)

    def columnCount(self, parent: QtCore.QModelIndex | None = None) -> int:  # type: ignore[override]
        return len(self._fields)

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.DisplayRole):  # type: ignore[override]
        if not index.isValid() or role not in (QtCore.Qt.DisplayRole, QtCore.Qt.EditRole):
            return None
        item = self._items[index.row()]
        attr = self._fields[index.column()]
        return getattr(item, attr)

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = QtCore.Qt.DisplayRole):  # type: ignore[override]
        if role != QtCore.Qt.DisplayRole or orientation != QtCore.Qt.Horizontal:
            return None
        return self._fields[section].replace("_", " ").title()

    def set_items(self, data: Iterable[object]) -> None:
        self.beginResetModel()
        self._items = list(data)
        self.endResetModel()


class PersonnelTableModel(BaseTableModel):  # type: ignore[misc]
    """Model that greys out demobilised personnel rows."""

    def data(self, index, role=QtCore.Qt.DisplayRole):  # type: ignore[override]
        value = super().data(index, role)
        if role == QtCore.Qt.ForegroundRole:
            item = self._items[index.row()]
            status = getattr(item, "checkin_status", None)
            if status == CheckInStatus.DEMOBILIZED:
                return QtCore.Qt.gray
        return value
