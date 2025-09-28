from __future__ import annotations

"""Qt Widgets panel for managing Incident Objectives."""

from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional

from PySide6.QtCore import (  # type: ignore[attr-defined]
    QAbstractTableModel,
    QModelIndex,
    QPoint,
    Qt,
    QSortFilterProxyModel,
)
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QHBoxLayout,
    QLineEdit,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QTableView,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from modules._infra.repository import with_incident_session
from modules.command.models.objectives import (
    ObjectiveFilters,
    ObjectiveRepository,
    ObjectiveSummary,
)
from modules.command.widgets.objective_detail_dialog import ObjectiveDetailDialog
from utils import incident_context, timefmt


TABLE_COLUMNS = [
    "#",
    "Objective",
    "Priority",
    "Status",
    "Owner/Section",
    "Strategies",
    "Open Tasks",
    "OP",
    "Updated",
]


class ObjectivesFilterProxyModel(QSortFilterProxyModel):
    """Simple proxy that filters using a case-insensitive search string."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._search_text = ""

    def set_search_text(self, text: str) -> None:
        self._search_text = text.lower().strip()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # type: ignore[override]
        if not self._search_text:
            return True
        model = self.sourceModel()
        if model is None:
            return True
        index = model.index(source_row, 1, source_parent)
        code_index = model.index(source_row, 0, source_parent)
        objective_text = str(model.data(index, Qt.DisplayRole) or "").lower()
        code_text = str(model.data(code_index, Qt.DisplayRole) or "").lower()
        return self._search_text in objective_text or self._search_text in code_text


class ObjectivesTableModel(QAbstractTableModel):
    """Table model driving the objectives grid."""

    def __init__(self, reorder_callback: Callable[[List[int]], None] | None = None) -> None:
        super().__init__()
        self._objectives: List[ObjectiveSummary] = []
        self._reorder_callback = reorder_callback

    # -- Qt model overrides -------------------------------------------------
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        if parent.isValid():
            return 0
        return len(self._objectives)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        if parent.isValid():
            return 0
        return len(TABLE_COLUMNS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.DisplayRole,
    ) -> object:  # type: ignore[override]
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            if 0 <= section < len(TABLE_COLUMNS):
                return TABLE_COLUMNS[section]
            return None
        return section + 1

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> object:  # type: ignore[override]
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        if row < 0 or row >= len(self._objectives):
            return None
        objective = self._objectives[row]
        if role == Qt.DisplayRole:
            if col == 0:
                return objective.display_order
            if col == 1:
                return objective.text
            if col == 2:
                return objective.priority.title()
            if col == 3:
                return objective.status.title()
            if col == 4:
                return objective.owner_section or ""
            if col == 5:
                return objective.strategies
            if col == 6:
                return objective.open_tasks
            if col == 7:
                return objective.op_period_id or ""
            if col == 8:
                if objective.updated_at:
                    return timefmt.relative_time(objective.updated_at)
                return ""
        if role == Qt.UserRole:
            return objective.id
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:  # type: ignore[override]
        base = super().flags(index)
        if not index.isValid():
            return base
        return base | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled | Qt.ItemIsSelectable | Qt.ItemIsEnabled

    def supportedDropActions(self) -> Qt.DropActions:  # type: ignore[override]
        return Qt.MoveAction

    def mimeTypes(self) -> List[str]:  # type: ignore[override]
        return ["application/x-incident-objective-row"]

    def mimeData(self, indexes: list[QModelIndex]):  # type: ignore[override]
        from PySide6.QtCore import QMimeData, QByteArray

        mime = QMimeData()
        if not indexes:
            return mime
        row = indexes[0].row()
        mime.setData("application/x-incident-objective-row", QByteArray(str(row).encode()))
        return mime

    def dropMimeData(
        self,
        data,
        action: Qt.DropAction,
        row: int,
        column: int,
        parent: QModelIndex,
    ) -> bool:  # type: ignore[override]
        if action != Qt.MoveAction:
            return False
        if not data.hasFormat("application/x-incident-objective-row"):
            return False
        try:
            source_row = int(bytes(data.data("application/x-incident-objective-row")).decode())
        except Exception:
            return False
        if row == -1:
            row = parent.row()
        if row == -1:
            row = self.rowCount()
        return self.moveRow(QModelIndex(), source_row, QModelIndex(), row)

    def moveRow(
        self,
        sourceParent: QModelIndex,
        sourceRow: int,
        destinationParent: QModelIndex,
        destinationChild: int,
    ) -> bool:  # type: ignore[override]
        return self.moveRows(sourceParent, sourceRow, 1, destinationParent, destinationChild)

    def moveRows(
        self,
        sourceParent: QModelIndex,
        sourceRow: int,
        count: int,
        destinationParent: QModelIndex,
        destinationChild: int,
    ) -> bool:  # type: ignore[override]
        if count != 1:
            return False
        if sourceRow < 0 or sourceRow >= len(self._objectives):
            return False
        if destinationChild > len(self._objectives):
            destinationChild = len(self._objectives)
        if sourceRow == destinationChild or sourceRow + 1 == destinationChild:
            return False
        self.beginMoveRows(sourceParent, sourceRow, sourceRow, destinationParent, destinationChild)
        objective = self._objectives.pop(sourceRow)
        insert_row = destinationChild
        if destinationChild > sourceRow:
            insert_row -= 1
        self._objectives.insert(insert_row, objective)
        self.endMoveRows()
        self._normalize_display_order()
        if self._reorder_callback:
            self._reorder_callback([obj.id for obj in self._objectives])
        return True

    # -- helpers ------------------------------------------------------------
    def set_objectives(self, objectives: Iterable[ObjectiveSummary]) -> None:
        self.beginResetModel()
        self._objectives = list(objectives)
        self.endResetModel()

    def objective_for_row(self, row: int) -> Optional[ObjectiveSummary]:
        if 0 <= row < len(self._objectives):
            return self._objectives[row]
        return None

    def _normalize_display_order(self) -> None:
        for idx, objective in enumerate(self._objectives):
            objective.display_order = idx


@dataclass
class _ToolbarWidgets:
    search: QLineEdit


class IncidentObjectivesPanel(QWidget):
    """Main QWidget surface for the Incident Objectives workspace."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._detail_windows: list[ObjectiveDetailDialog] = []
        self._toolbar = QToolBar("Objectives", self)
        self._toolbar.setIconSize(self._toolbar.iconSize())
        self._toolbar.setMovable(False)

        layout = QVBoxLayout(self)
        layout.addWidget(self._toolbar)

        toolbar_widgets = self._build_toolbar()

        table_container = QWidget(self)
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        self._table = QTableView(table_container)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setSortingEnabled(True)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setDragDropMode(QAbstractItemView.InternalMove)
        self._table.setDragDropOverwriteMode(False)
        self._table.setDefaultDropAction(Qt.MoveAction)

        self._model = ObjectivesTableModel(self._persist_reorder)
        self._proxy = ObjectivesFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._table.setModel(self._proxy)
        header = self._table.horizontalHeader()
        header.setSectionsMovable(True)
        header.setStretchLastSection(True)

        self._table.doubleClicked.connect(self._on_double_clicked)
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)

        table_layout.addWidget(self._table)
        layout.addWidget(table_container)

        toolbar_widgets.search.textChanged.connect(self._proxy.set_search_text)

        self.reload()

    # ------------------------------------------------------------------
    def _build_toolbar(self) -> _ToolbarWidgets:
        new_action = QAction(QIcon.fromTheme("list-add"), "New Objective", self)
        new_action.triggered.connect(self._create_objective)
        self._toolbar.addAction(new_action)

        clone_action = QAction("Clone From Previous OP", self)
        clone_action.triggered.connect(self._clone_previous)
        self._toolbar.addAction(clone_action)

        reorder_action = QAction("Reorder", self)
        reorder_action.triggered.connect(self._prompt_reorder_help)
        self._toolbar.addAction(reorder_action)

        self._toolbar.addSeparator()

        search_edit = QLineEdit(self)
        search_edit.setPlaceholderText("Search objectives…")
        search_edit.setClearButtonEnabled(True)
        search_edit.setMaximumWidth(260)
        self._toolbar.addWidget(search_edit)

        filters_action = QAction("Filters", self)
        filters_action.triggered.connect(self._show_filters_dialog)
        self._toolbar.addAction(filters_action)

        export_button = QToolButton(self)
        export_button.setText("Export")
        export_button.setPopupMode(QToolButton.MenuButtonPopup)
        export_menu = QMenu(export_button)
        export_menu.addAction("ICS-202", self._export_ics202)
        export_button.setMenu(export_menu)
        export_button.clicked.connect(self._export_ics202)
        self._toolbar.addWidget(export_button)

        print_action = QAction("Print Preview", self)
        print_action.triggered.connect(self._show_print_preview)
        self._toolbar.addAction(print_action)

        spacer = QWidget(self)
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._toolbar.addWidget(spacer)
        return _ToolbarWidgets(search=search_edit)

    # ------------------------------------------------------------------
    def reload(self) -> None:
        incident_id = incident_context.get_active_incident()
        if not incident_id:
            self._model.set_objectives([])
            return
        try:
            with with_incident_session(str(incident_id)) as session:
                repository = ObjectiveRepository(session, str(incident_id))
                objectives = repository.list_objectives(ObjectiveFilters())
        except Exception as exc:  # pragma: no cover - UI fallback
            QMessageBox.critical(self, "Incident Objectives", f"Failed to load objectives:\n{exc}")
            objectives = []
        self._model.set_objectives(objectives)
        if self._table.model() is self._proxy:
            self._table.sortByColumn(0, Qt.AscendingOrder)

    # ------------------------------------------------------------------
    def _create_objective(self) -> None:
        dialog = ObjectiveDetailDialog(self)
        dialog.setWindowTitle("New Objective")
        dialog.show()
        self._detail_windows.append(dialog)

    def _clone_previous(self) -> None:
        QMessageBox.information(
            self,
            "Clone Objectives",
            "Cloning from the previous operational period is not yet implemented.",
        )

    def _prompt_reorder_help(self) -> None:
        QMessageBox.information(
            self,
            "Reorder Objectives",
            "Drag rows in the table to change their display order.",
        )

    def _show_filters_dialog(self) -> None:
        QMessageBox.information(
            self,
            "Filters",
            "Advanced filters will be available in a future update.",
        )

    def _export_ics202(self) -> None:
        incident_id = incident_context.get_active_incident()
        if not incident_id:
            QMessageBox.warning(self, "Export", "Select an incident to export ICS-202 data.")
            return
        try:
            with with_incident_session(str(incident_id)) as session:
                repository = ObjectiveRepository(session, str(incident_id))
                payload = repository.export_ics202()
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Export", f"Failed to build ICS-202 export:\n{exc}")
            return
        QMessageBox.information(
            self,
            "Export",
            "ICS-202 payload prepared. Hand-off to Forms module pending integration.",
        )
        print(payload)  # noqa: T201

    def _show_print_preview(self) -> None:
        QMessageBox.information(
            self,
            "Print Preview",
            "Print preview is not yet implemented for the Objectives panel.",
        )

    def _on_double_clicked(self, index: QModelIndex) -> None:
        self._open_detail_for_index(index)

    def _show_context_menu(self, pos: QPoint) -> None:
        index = self._table.indexAt(pos)
        if not index.isValid():
            return
        menu = QMenu(self._table)
        menu.addAction("Edit", lambda: self._open_detail_for_index(index))
        menu.addAction("Quick Status", lambda: self._quick_status(index))
        menu.addSeparator()
        menu.addAction("Add Strategy", lambda: self._open_detail_for_index(index))
        menu.addAction("Create Task", lambda: self._open_detail_for_index(index))
        menu.addAction("View All Tasks", lambda: self._open_detail_for_index(index))
        menu.addAction("Duplicate", lambda: self._duplicate_objective(index))
        menu.addAction("Complete/Cancel", lambda: self._quick_status(index, target="completed"))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _open_detail_for_index(self, proxy_index: QModelIndex) -> None:
        source_index = self._proxy.mapToSource(proxy_index)
        objective = self._model.objective_for_row(source_index.row())
        if not objective:
            return
        dialog = ObjectiveDetailDialog(self)
        dialog.load_objective(objective.id)
        dialog.show()
        self._detail_windows.append(dialog)

    def _quick_status(self, proxy_index: QModelIndex, target: str | None = None) -> None:
        source_index = self._proxy.mapToSource(proxy_index)
        objective = self._model.objective_for_row(source_index.row())
        if not objective:
            return
        incident_id = incident_context.get_active_incident()
        if not incident_id:
            return
        next_status = target or ("active" if objective.status != "active" else "completed")
        try:
            with with_incident_session(str(incident_id)) as session:
                repository = ObjectiveRepository(session, str(incident_id))
                repository.set_status(objective.id, next_status)
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Quick Status", f"Failed to update status:\n{exc}")
            return
        self.reload()

    def _duplicate_objective(self, proxy_index: QModelIndex) -> None:
        QMessageBox.information(
            self,
            "Duplicate Objective",
            "Objective duplication is not yet available.",
        )

    def _persist_reorder(self, ordered_ids: List[int]) -> None:
        incident_id = incident_context.get_active_incident()
        if not incident_id:
            return
        try:
            with with_incident_session(str(incident_id)) as session:
                repository = ObjectiveRepository(session, str(incident_id))
                repository.reorder_objectives(ordered_ids)
        except Exception as exc:  # pragma: no cover
            QMessageBox.warning(self, "Reorder", f"Failed to persist order:\n{exc}")

