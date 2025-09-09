from __future__ import annotations

from typing import Any, Dict, List, Sequence

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt


class SimpleListModel(QAbstractListModel):
    """Generic list model exposing rows of dictionaries to QML.

    The model is initialised with a sequence of role names; each row is a
    ``dict`` mapping those role names to values.  Convenience methods ``replace``
    and ``append`` are provided for bulk updates.
    """

    def __init__(self, roles: Sequence[str], rows: List[Dict[str, Any]] | None = None, parent=None) -> None:
        super().__init__(parent)
        self._roles = list(roles)
        self._data: List[Dict[str, Any]] = rows or []
        self._role_map = {Qt.UserRole + i + 1: role.encode() for i, role in enumerate(self._roles)}

    # Qt model interface -------------------------------------------------
    def rowCount(self, parent: QModelIndex | None = QModelIndex()) -> int:  # type: ignore[override]
        return len(self._data)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:  # type: ignore[override]
        if not index.isValid() or role < Qt.UserRole + 1:
            return None
        key = self._roles[role - Qt.UserRole - 1]
        return self._data[index.row()].get(key)

    def roleNames(self) -> Dict[int, bytes]:  # type: ignore[override]
        return self._role_map

    # Convenience API ----------------------------------------------------
    def replace(self, rows: List[Dict[str, Any]]) -> None:
        """Replace the entire model contents with ``rows``."""
        self.beginResetModel()
        self._data = list(rows)
        self.endResetModel()

    def append(self, row: Dict[str, Any]) -> None:
        """Append a single row to the model."""
        position = len(self._data)
        self.beginInsertRows(QModelIndex(), position, position)
        self._data.append(row)
        self.endInsertRows()


class ObjectiveListModel(SimpleListModel):
    """List model for incident objectives shown in the objective panel."""

    def __init__(self, rows: List[Dict[str, Any]] | None = None, parent=None) -> None:
        # Use 'oid' instead of 'id' to avoid clashing with QML 'id' keyword in delegates
        # Include description and section so list and details can render without extra queries
        roles = ["oid", "code", "description", "priority", "status", "customer", "section", "due"]
        super().__init__(roles, rows or [], parent)
