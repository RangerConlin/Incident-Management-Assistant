"""Audit trail view widget."""

from __future__ import annotations

from PySide6 import QtWidgets


class AuditView(QtWidgets.QTreeWidget):
    """Displays audit entries in a simple tree widget."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setColumnCount(4)
        self.setHeaderLabels(["Timestamp", "Entity", "Field", "New Value"])
        self.setAlternatingRowColors(True)
        self.setRootIsDecorated(False)

    def set_entries(self, entries: list[dict[str, object]]) -> None:
        self.clear()
        for entry in entries:
            item = QtWidgets.QTreeWidgetItem(
                [
                    str(entry.get("ts_utc", "")),
                    str(entry.get("entity_type", "")),
                    str(entry.get("field", "")),
                    str(entry.get("new_value", "")),
                ]
            )
            item.setToolTip(3, str(entry.get("new_value", "")))
            self.addTopLevelItem(item)
        self.resizeColumnToContents(0)
        self.resizeColumnToContents(1)
