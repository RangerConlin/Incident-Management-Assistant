"""Reusable filterable, checkable list widget used by hazard linking/op-period pickers."""

from __future__ import annotations

from typing import Any, Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget


class CheckableList(QWidget):
    """A search-filterable list of checkable items, keyed by an integer id."""

    def __init__(
        self,
        items: list[dict[str, Any]],
        id_key: str,
        label_fn: Callable[[dict[str, Any]], str],
        selected_ids: set[int],
        *,
        show_filter: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if show_filter:
            self.search = QLineEdit(self)
            self.search.setPlaceholderText("Filter...")
            self.search.textChanged.connect(self._filter)
            layout.addWidget(self.search)

        self.list_widget = QListWidget(self)
        layout.addWidget(self.list_widget)

        for item in items:
            item_id = int(item.get(id_key, 0))
            list_item = QListWidgetItem(label_fn(item))
            list_item.setData(Qt.UserRole, item_id)
            list_item.setCheckState(Qt.Checked if item_id in selected_ids else Qt.Unchecked)
            self.list_widget.addItem(list_item)

    def _filter(self, text: str) -> None:
        text = text.strip().lower()
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            item.setHidden(bool(text) and text not in item.text().lower())

    def selected_ids(self) -> list[int]:
        result = []
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            if item.checkState() == Qt.Checked:
                result.append(int(item.data(Qt.UserRole)))
        return result
