from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSizePolicy,
    QTableView,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QSortFilterProxyModel,
)

from .widgets import SearchLineEdit


@dataclass
class ColumnSpec:
    field: str
    header: str


class DictTableModel(QAbstractTableModel):
    """Simple table model backed by a list of dictionaries."""

    def __init__(self, columns: Sequence[ColumnSpec], rows: list[dict[str, Any]]):
        super().__init__()
        self._columns = columns
        self._rows = rows

    # Qt model interface -------------------------------------------------
    def rowCount(self, parent: QModelIndex | None = None) -> int:  # pragma: no cover - trivial
        return 0 if parent and parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # pragma: no cover - trivial
        return 0 if parent and parent.isValid() else len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):  # pragma: no cover - trivial
        if not index.isValid() or role not in {Qt.DisplayRole, Qt.EditRole}:
            return None
        row = self._rows[index.row()]
        col = self._columns[index.column()].field
        return row.get(col)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):  # pragma: no cover - trivial
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self._columns[section].header
        return section + 1

    # helpers ------------------------------------------------------------
    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def row(self, index: int) -> dict[str, Any]:
        return self._rows[index]


class BaseEditDialog(QDialog):
    """Reusable framework providing CRUD scaffolding for master data editors."""

    recordAdded = Signal(dict)
    recordUpdated = Signal(dict)
    recordDeleted = Signal(int)
    saved = Signal()

    def __init__(self, title: str, description: str | None = None, parent: QWidget | None = None, *, modal: bool = False):
        super().__init__(parent)
        if modal:
            self.setModal(True)
        self.setWindowTitle(title)
        self._description = description
        self._columns: list[ColumnSpec] = []
        self._adapter: Any = None
        self._current_id: Any = None
        self._dirty = False

        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        if self._description:
            lab = QLabel(self._description)
            lab.setWordWrap(True)
            layout.addWidget(lab)

        # Toolbar -------------------------------------------------------
        self.toolbar = QToolBar()
        self.act_add = self.toolbar.addAction("Add")
        self.act_edit = self.toolbar.addAction("Edit")
        self.act_delete = self.toolbar.addAction("Delete")
        self.toolbar.addSeparator()
        self.act_save = self.toolbar.addAction("Save")
        self.act_cancel = self.toolbar.addAction("Cancel")
        layout.addWidget(self.toolbar)

        # Search --------------------------------------------------------
        self.search = SearchLineEdit()
        layout.addWidget(self.search)

        # Table + form --------------------------------------------------
        hl = QHBoxLayout()
        layout.addLayout(hl)

        self.table = QTableView()
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.doubleClicked.connect(self._on_edit)
        hl.addWidget(self.table, 2)

        self.form_widget = QWidget()
        self.form_layout = QFormLayout(self.form_widget)
        self.form_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        hl.addWidget(self.form_widget, 1)

        # Connections ---------------------------------------------------
        self.act_add.triggered.connect(self._on_add)
        self.act_edit.triggered.connect(self._on_edit)
        self.act_delete.triggered.connect(self._on_delete)
        self.act_save.triggered.connect(self._on_save)
        self.act_cancel.triggered.connect(self._on_cancel)
        self.search.textChanged.connect(self._on_search)

        # Shortcuts
        self.act_save.setShortcut(QKeySequence.Save)
        self.search.setShortcut(QKeySequence.Find)
        self.table.addAction(self.act_delete)

        self._update_action_states()

    # ------------------------------------------------------------------ configuration
    def set_columns(self, columns: Iterable[tuple[str, str]]) -> None:
        self._columns = [ColumnSpec(*c) for c in columns]
        self._model = DictTableModel(self._columns, [])
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)  # search all
        self.table.setModel(self._proxy)

    def set_adapter(self, adapter: Any) -> None:
        self._adapter = adapter
        self.refresh()

    def set_form_widget(self, widget: QWidget) -> None:
        self.form_widget.deleteLater()
        self.form_widget = widget
        self.form_layout = getattr(widget, "layout", QFormLayout)()

    # ------------------------------------------------------------------ adapter helpers
    def refresh(self) -> None:
        if self._adapter is None:
            return
        rows = list(self._adapter.list())
        self._model.set_rows(rows)
        self.table.resizeColumnsToContents()
        self._update_action_states()

    # ------------------------------------------------------------------ actions
    def _on_add(self) -> None:
        self._current_id = None
        self._populate_form({})
        self._dirty = True
        self._update_action_states()

    def _on_edit(self) -> None:
        idx = self.table.currentIndex()
        if not idx.isValid():
            return
        src = self._proxy.mapToSource(idx)
        record = self._model.row(src.row())
        self._current_id = record.get("id")
        self._populate_form(record)
        self._dirty = True
        self._update_action_states()

    def _on_delete(self) -> None:
        idx = self.table.currentIndex()
        if not idx.isValid() or self._adapter is None:
            return
        src = self._proxy.mapToSource(idx)
        record = self._model.row(src.row())
        if QMessageBox.question(self, "Delete", f"Delete record '{record}'?") == QMessageBox.Yes:
            self._adapter.delete(record["id"])
            self.recordDeleted.emit(record["id"])
            self.refresh()

    def _on_save(self) -> None:
        if self._adapter is None:
            return
        payload = self._collect_form()
        if self._current_id is None:
            new_id = self._adapter.create(payload)
            payload["id"] = new_id
            self.recordAdded.emit(payload)
        else:
            self._adapter.update(self._current_id, payload)
            payload["id"] = self._current_id
            self.recordUpdated.emit(payload)
        self._dirty = False
        self.refresh()
        self.saved.emit()

    def _on_cancel(self) -> None:
        self._populate_form({})
        self._current_id = None
        self._dirty = False
        self._update_action_states()

    def _on_search(self, text: str) -> None:
        self._proxy.setFilterFixedString(text)

    # ------------------------------------------------------------------ utilities for subclasses
    def _populate_form(self, record: dict[str, Any]) -> None:
        """Subclasses should override to map record -> form widgets."""
        pass

    def _collect_form(self) -> dict[str, Any]:
        """Subclasses should override to map form widgets -> payload."""
        return {}

    # ------------------------------------------------------------------ housekeeping
    def _update_action_states(self) -> None:
        has_selection = self.table.currentIndex().isValid()
        self.act_edit.setEnabled(has_selection)
        self.act_delete.setEnabled(has_selection)
        self.act_save.setEnabled(self._dirty)
        self.act_cancel.setEnabled(self._dirty)

    def closeEvent(self, event):  # pragma: no cover - requires GUI
        if self._dirty and QMessageBox.question(self, "Unsaved", "Discard changes?") != QMessageBox.Yes:
            event.ignore()
            return
        super().closeEvent(event)
