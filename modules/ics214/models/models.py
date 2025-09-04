from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QByteArray


@dataclass
class ICS214Entry:
    """Simple container for an ICS 214 log entry."""

    when: str
    entered_by: str
    entry: str
    target: str
    source: str
    critical: bool
    tags: Sequence[str]


class ICS214Model(QAbstractTableModel):
    """Basic table model for ICS 214 Activity Log entries."""

    headers = [
        "Time",
        "Entered By",
        "Entry",
        "Target",
        "Source",
        "Critical",
        "Tags",
    ]

    TimeRole = Qt.UserRole + 1
    EnteredByRole = Qt.UserRole + 2
    EntryRole = Qt.UserRole + 3
    TargetRole = Qt.UserRole + 4
    SourceRole = Qt.UserRole + 5
    CriticalRole = Qt.UserRole + 6
    TagsRole = Qt.UserRole + 7

    def __init__(
        self, entries: Sequence[ICS214Entry] | None = None, parent=None
    ) -> None:
        super().__init__(parent)
        self._entries: List[ICS214Entry] = list(entries or [])

    # --- Qt model API -------------------------------------------------
    def rowCount(
        self, parent: QModelIndex = QModelIndex()
    ) -> int:  # type: ignore[override]
        return 0 if parent.isValid() else len(self._entries)

    def columnCount(
        self, parent: QModelIndex = QModelIndex()
    ) -> int:  # type: ignore[override]
        return 0 if parent.isValid() else len(self.headers)

    def data(
        self, index: QModelIndex, role: int = Qt.DisplayRole
    ) -> Any:  # type: ignore[override]
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        if row < 0 or row >= len(self._entries):
            return None
        entry = self._entries[row]

        if role in (Qt.DisplayRole, Qt.EditRole):
            return [
                entry.when,
                entry.entered_by,
                entry.entry,
                entry.target,
                entry.source,
                "Yes" if entry.critical else "",
                ",".join(entry.tags),
            ][col]
        if role == self.TimeRole:
            return entry.when
        if role == self.EnteredByRole:
            return entry.entered_by
        if role == self.EntryRole:
            return entry.entry
        if role == self.TargetRole:
            return entry.target
        if role == self.SourceRole:
            return entry.source
        if role == self.CriticalRole:
            return entry.critical
        if role == self.TagsRole:
            return list(entry.tags)
        return None

    def roleNames(self):  # type: ignore[override]
        return {
            self.TimeRole: QByteArray(b"time"),
            self.EnteredByRole: QByteArray(b"enteredBy"),
            self.EntryRole: QByteArray(b"entry"),
            self.TargetRole: QByteArray(b"target"),
            self.SourceRole: QByteArray(b"source"),
            self.CriticalRole: QByteArray(b"critical"),
            self.TagsRole: QByteArray(b"tags"),
        }

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.DisplayRole,
    ) -> Any:  # type: ignore[override]
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            if 0 <= section < len(self.headers):
                return self.headers[section]
            return None
        return section + 1

    # --- API ----------------------------------------------------------
    def set_entries(self, entries: Sequence[ICS214Entry]) -> None:
        self.beginResetModel()
        self._entries = list(entries)
        self.endResetModel()

    def entry(self, row: int) -> ICS214Entry | None:
        if 0 <= row < len(self._entries):
            return self._entries[row]
        return None
