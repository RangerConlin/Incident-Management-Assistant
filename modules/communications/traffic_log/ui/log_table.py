"""Table model and view for the communications traffic log."""

from __future__ import annotations

from typing import Iterable, List, Optional, Set

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import QHeaderView, QTableView

from ..models import (
    CommsLogEntry,
    PRIORITY_EMERGENCY,
    PRIORITY_PRIORITY,
    PRIORITY_ROUTINE,
)


PRIORITY_PALETTE = {
    PRIORITY_EMERGENCY: (QColor("#FDECEA"), QColor("#7A1E1E")),
    PRIORITY_PRIORITY: (QColor("#FFF4E5"), QColor("#6A4B00")),
    PRIORITY_ROUTINE: (QColor("#EEF2FF"), QColor("#1F2937")),
}


class CommsLogTableModel(QAbstractTableModel):
    """QAbstractTableModel representing log entries."""

    headers = [
        "Timestamp",
        "Priority",
        "Channel/Resource",
        "Frequency",
        "Band",
        "Mode",
        "From",
        "To",
        "Message",
        "Action Taken",
        "Follow-up",
        "Disposition",
        "Operator",
        "Related",
        "Attachments",
        "Geotag",
        "Notification",
        "Status Update",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries: List[CommsLogEntry] = []
        self._use_utc = False

    # Basic model API --------------------------------------------------
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        if parent.isValid():
            return 0
        return len(self._entries)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return len(self.headers)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):  # type: ignore[override]
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            try:
                return self.headers[section]
            except IndexError:
                return None
        return section + 1

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None
        entry = self._entries[index.row()]
        column = index.column()
        if role == Qt.DisplayRole:
            return self._display_value(entry, column)
        if role == Qt.ToolTipRole:
            return self._tooltip_value(entry, column)
        if role == Qt.BackgroundRole:
            bg, _ = PRIORITY_PALETTE.get(entry.priority, (None, None))
            if bg is not None:
                return QBrush(bg)
        if role == Qt.ForegroundRole:
            _, fg = PRIORITY_PALETTE.get(entry.priority, (None, None))
            if fg is not None:
                return QBrush(fg)
        return None

    # Helpers ----------------------------------------------------------
    def _display_value(self, entry: CommsLogEntry, column: int) -> str:
        if column == 0:
            return entry.ts_utc if self._use_utc else entry.ts_local
        if column == 1:
            return entry.priority
        if column == 2:
            return entry.resource_label
        if column == 3:
            return entry.frequency
        if column == 4:
            return entry.band
        if column == 5:
            return entry.mode
        if column == 6:
            return entry.from_unit
        if column == 7:
            return entry.to_unit
        if column == 8:
            return entry.message
        if column == 9:
            return entry.action_taken
        if column == 10:
            return "Yes" if entry.follow_up_required else "No"
        if column == 11:
            return entry.disposition
        if column == 12:
            return entry.operator_user_id or ""
        if column == 13:
            related_parts = []
            if entry.task_id:
                related_parts.append(f"Task {entry.task_id}")
            if entry.team_id:
                related_parts.append(f"Team {entry.team_id}")
            if entry.vehicle_id:
                related_parts.append(f"Vehicle {entry.vehicle_id}")
            if entry.personnel_id:
                related_parts.append(f"Personnel {entry.personnel_id}")
            return ", ".join(related_parts)
        if column == 14:
            return str(len(entry.attachments)) if entry.attachments else ""
        if column == 15:
            if entry.geotag_lat is not None and entry.geotag_lon is not None:
                return f"{entry.geotag_lat:.5f}, {entry.geotag_lon:.5f}"
            return ""
        if column == 16:
            return entry.notification_level or ""
        if column == 17:
            return "Yes" if entry.is_status_update else "No"
        return ""

    def _tooltip_value(self, entry: CommsLogEntry, column: int) -> Optional[str]:
        if column in (8, 9):
            return self._display_value(entry, column)
        if column == 14 and entry.attachments:
            return "\n".join(entry.attachments)
        return None

    # Public API -------------------------------------------------------
    def set_entries(self, entries: List[CommsLogEntry]) -> None:
        self.beginResetModel()
        self._entries = list(entries)
        self.endResetModel()

    def entry_at(self, row: int) -> Optional[CommsLogEntry]:
        if 0 <= row < len(self._entries):
            return self._entries[row]
        return None

    def set_use_utc(self, value: bool) -> None:
        if self._use_utc == value:
            return
        self._use_utc = value
        if self._entries:
            top_left = self.index(0, 0)
            bottom_right = self.index(len(self._entries) - 1, 0)
            self.dataChanged.emit(top_left, bottom_right, [Qt.DisplayRole])
        else:
            self.layoutChanged.emit()


class CommsLogTableView(QTableView):
    """Table view wrapper with sensible defaults."""

    DEFAULT_VISIBLE_COLUMNS: Set[str] = {"Timestamp", "From", "To", "Message", "Notification"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableView.SelectRows)
        self.setSelectionMode(QTableView.SingleSelection)
        self.setSortingEnabled(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.verticalHeader().setVisible(False)
        self.setWordWrap(False)
        self.setModel(CommsLogTableModel(self))
        self._column_indices = {label: idx for idx, label in enumerate(self.model.headers)}
        self._visible_columns: Set[str] = set(self.DEFAULT_VISIBLE_COLUMNS)
        if not self._visible_columns:
            self._visible_columns = set(self._column_indices.keys())
        self._apply_column_visibility()

    @property
    def model(self) -> CommsLogTableModel:  # type: ignore[override]
        return super().model()  # type: ignore[return-value]

    def set_entries(self, entries: List[CommsLogEntry]) -> None:
        self.model.set_entries(entries)
        if entries:
            self.selectRow(0)

    def selected_entry(self) -> Optional[CommsLogEntry]:
        index = self.selectionModel().currentIndex()
        if not index.isValid():
            return None
        return self.model.entry_at(index.row())

    # Column visibility -------------------------------------------------
    def column_labels(self) -> List[str]:
        return list(self._column_indices.keys())

    def visible_columns(self) -> Set[str]:
        return set(self._visible_columns)

    def set_visible_columns(self, columns: Iterable[str]) -> None:
        selection = {col for col in columns if col in self._column_indices}
        if not selection:
            # Ensure at least one column remains visible
            selection = {next(iter(self._column_indices.keys()))}
        self._visible_columns = selection
        self._apply_column_visibility()

    def set_column_visible(self, column: str, visible: bool) -> bool:
        if column not in self._column_indices:
            return False
        if visible:
            self._visible_columns.add(column)
            self._apply_column_visibility()
            return True
        if column in self._visible_columns and len(self._visible_columns) > 1:
            self._visible_columns.remove(column)
            self._apply_column_visibility()
            return True
        return False

    def _apply_column_visibility(self) -> None:
        if not hasattr(self, "_column_indices"):
            return
        for name, index in self._column_indices.items():
            self.setColumnHidden(index, name not in self._visible_columns)


__all__ = ["CommsLogTableModel", "CommsLogTableView"]
