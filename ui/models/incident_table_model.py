from __future__ import annotations

"""Qt table model for incident rows.

This model is intentionally lightweight and schema-agnostic.  Columns are
inferred from the first row provided.  Preferred columns are ordered first but
any additional columns from the database are appended to ensure nothing is
lost.
"""

from datetime import datetime
from typing import Iterable, List, Dict, Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


_PREFERRED_ORDER = [
    "id",
    "name",
    "type",
    "status",
    "start_date",
    "end_date",
    "is_active",
    "created_at",
    "updated_at",
]


class IncidentTableModel(QAbstractTableModel):
    """Simple table model mapping incident dictionaries to Qt."""

    def __init__(self, rows: Iterable[Dict[str, Any]] | None = None, parent=None) -> None:
        super().__init__(parent)
        self._rows: List[Dict[str, Any]] = list(rows or [])
        self._columns: List[str] = []
        if self._rows:
            self._columns = self._derive_columns(self._rows[0].keys())

    # ------------------------------------------------------------------
    @property
    def columns(self) -> List[str]:
        return list(self._columns)

    # ------------------------------------------------------------------
    def _derive_columns(self, keys: Iterable[str]) -> List[str]:
        keys = list(keys)
        ordered: List[str] = [c for c in _PREFERRED_ORDER if c in keys]
        ordered.extend([k for k in keys if k not in ordered])
        return ordered

    # ------------------------------------------------------------------
    def refresh(self, rows: Iterable[Dict[str, Any]]) -> None:
        rows = list(rows)
        self.beginResetModel()
        self._rows = rows
        self._columns = self._derive_columns(rows[0].keys()) if rows else []
        self.endResetModel()

    # Qt model API ------------------------------------------------------
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return 0 if parent.isValid() else len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):  # type: ignore[override]
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        col = self._columns[index.column()]
        row = self._rows[index.row()]
        value = row.get(col)
        if role in (Qt.DisplayRole, Qt.EditRole):
            return self._format_value(value)
        return value

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):  # type: ignore[override]
        if role != Qt.DisplayRole or orientation != Qt.Horizontal:
            return super().headerData(section, orientation, role)
        if 0 <= section < len(self._columns):
            return self._columns[section].replace("_", " ").title()
        return super().headerData(section, orientation, role)

    def flags(self, index: QModelIndex):  # type: ignore[override]
        base = super().flags(index)
        return base & ~Qt.ItemIsEditable

    # ------------------------------------------------------------------
    def _format_value(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, (int, float)) and value in (0, 1) and isinstance(value, (int, bool)):
            # for numeric boolean fields
            return "Yes" if int(value) else "No"
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value)
                if dt.time().hour == 0 and dt.time().minute == 0 and dt.time().second == 0:
                    return dt.strftime("%Y-%m-%d")
                return dt.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                return value
        return str(value)

    # Convenience -------------------------------------------------------
    def row_dict(self, row: int) -> Dict[str, Any]:
        return self._rows[row]


__all__ = ["IncidentTableModel"]
