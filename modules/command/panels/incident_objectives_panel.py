from __future__ import annotations

"""Qt Widgets panel for managing Incident Objectives."""

from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPoint,
    Qt,
    QSortFilterProxyModel,
)
from PySide6.QtGui import QAction, QIcon, QTextDocument
from PySide6.QtPrintSupport import QPrintPreviewDialog, QPrinter
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

from modules.command.models.objectives import (
    ApiObjectiveRepository,
    ObjectiveFilters,
    ObjectiveSummary,
)
from modules.command.widgets.objective_detail_dialog import ObjectiveDetailDialog
from modules.command.widgets.objective_template_picker_dialog import ObjectiveTemplatePickerDialog
from modules.planning.operational_periods.repository import OperationalPeriodRepository
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
                return objective.code
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

        template_action = QAction("New From Template…", self)
        template_action.triggered.connect(self._create_from_template)
        self._toolbar.addAction(template_action)

        manage_templates_action = QAction("Manage Templates…", self)
        manage_templates_action.triggered.connect(self._open_template_manager)
        self._toolbar.addAction(manage_templates_action)

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
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            self._model.set_objectives([])
            return
        try:
            objectives = ApiObjectiveRepository(str(incident_id)).list_objectives(ObjectiveFilters())
        except Exception as exc:  # pragma: no cover - UI fallback
            QMessageBox.critical(self, "Incident Objectives", f"Failed to load objectives:\n{exc}")
            objectives = []
        self._model.set_objectives(objectives)
        if self._table.model() is self._proxy:
            self._table.sortByColumn(0, Qt.AscendingOrder)

    # ------------------------------------------------------------------
    def _create_objective(self) -> None:
        dialog = ObjectiveDetailDialog(self, on_saved=self.reload)
        dialog.setWindowTitle("New Objective")
        dialog.show()
        self._detail_windows.append(dialog)

    def _create_from_template(self) -> None:
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            QMessageBox.warning(self, "New From Template", "Select an incident first.")
            return
        dialog = ObjectiveTemplatePickerDialog(self, on_imported=self.reload)
        dialog.exec()

    def _open_template_manager(self) -> None:
        from modules.planning.widgets.objectives_editor import show_objectives_editor
        editor = show_objectives_editor(None)
        editor.raise_()
        editor.activateWindow()

    def _clone_previous(self) -> None:
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            QMessageBox.warning(self, "Clone Objectives", "Select an incident to clone objectives.")
            return
        try:
            op_repo = OperationalPeriodRepository(str(incident_id))
            periods = sorted(op_repo.list_periods(), key=lambda p: p.number)
        except Exception as exc:  # pragma: no cover - UI fallback
            QMessageBox.critical(self, "Clone Objectives", f"Failed to load operational periods:\n{exc}")
            return
        if len(periods) < 2:
            QMessageBox.information(self, "Clone Objectives", "There is no previous operational period to clone from.")
            return
        active = op_repo.get_active_period()
        if active is not None:
            earlier = [p for p in periods if p.number < active.number]
            if not earlier:
                QMessageBox.information(self, "Clone Objectives", "There is no operational period before the active one.")
                return
            target = active
            source = earlier[-1]
        else:
            target = periods[-1]
            source = periods[-2]

        try:
            objectives = ApiObjectiveRepository(str(incident_id)).list_objectives(
                ObjectiveFilters(op_period_id=source.id)
            )
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Clone Objectives", f"Failed to load source objectives:\n{exc}")
            return
        if not objectives:
            QMessageBox.information(self, "Clone Objectives", f"OP {source.number} has no objectives to clone.")
            return

        confirm = QMessageBox.question(
            self,
            "Clone Objectives",
            f"Clone {len(objectives)} objective(s) from OP {source.number} into OP {target.number}?",
        )
        if confirm != QMessageBox.Yes:
            return

        repo = ApiObjectiveRepository(str(incident_id))
        failures = 0
        for objective in objectives:
            try:
                repo.create_objective(
                    {
                        "text": objective.text,
                        "priority": objective.priority,
                        "status": "draft",
                        "owner_section": objective.owner_section,
                        "op_period_id": target.id,
                        "tags": list(objective.tags),
                    }
                )
            except Exception:
                failures += 1
        self.reload()
        if failures:
            QMessageBox.warning(self, "Clone Objectives", f"Cloned with {failures} failure(s). See logs for details.")
        else:
            QMessageBox.information(self, "Clone Objectives", f"Cloned {len(objectives)} objective(s) into OP {target.number}.")

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
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            QMessageBox.warning(self, "Export", "Select an incident to export ICS-202 data.")
            return
        try:
            payload = ApiObjectiveRepository(str(incident_id)).export_ics202()
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Export", f"Failed to build ICS-202 export:\n{exc}")
            return
        try:
            from pathlib import Path
            from utils import incident_storage
            from modules.forms_creator.api import export_form_unified

            paths = incident_storage.resolve_incident_paths_by_identifier(str(incident_id))
            out_dir = paths.forms_exports if paths else Path("data") / "exports" / str(incident_id)
            out_dir.mkdir(parents=True, exist_ok=True)
            result = export_form_unified(
                "ics_202",
                out_dir / "ICS202.pdf",
                values=payload if isinstance(payload, dict) else {},
                context={"incident_id": str(incident_id)},
            )
            QMessageBox.information(self, "Export", f"ICS-202 exported to:\n{result.path}")
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Export", f"Export failed:\n{exc}")

    def _show_print_preview(self) -> None:
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            QMessageBox.warning(self, "Print Preview", "Select an incident to preview objectives.")
            return
        try:
            payload = ApiObjectiveRepository(str(incident_id)).export_ics202()
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Print Preview", f"Failed to build preview:\n{exc}")
            return

        document = QTextDocument(self)
        document.setHtml(self._build_preview_html(payload))
        printer = QPrinter(QPrinter.HighResolution)
        preview = QPrintPreviewDialog(printer, self)
        preview.setWindowTitle("Incident Objectives — Print Preview")
        preview.paintRequested.connect(document.print_)
        preview.exec()

    @staticmethod
    def _build_preview_html(payload: dict) -> str:
        rows = []
        for obj in payload.get("objectives", []):
            rows.append(
                "<tr>"
                f"<td>{obj.get('order', '')}</td>"
                f"<td>{obj.get('code', '')}</td>"
                f"<td>{obj.get('text', '')}</td>"
                f"<td>{obj.get('priority', '').title()}</td>"
                f"<td>{obj.get('status', '').title()}</td>"
                "</tr>"
            )
        return (
            "<h2>Incident Objectives (ICS-202)</h2>"
            "<table border='1' cellspacing='0' cellpadding='4' width='100%'>"
            "<tr><th>#</th><th>Code</th><th>Objective</th><th>Priority</th><th>Status</th></tr>"
            + "".join(rows)
            + "</table>"
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
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            return
        next_status = target or ("active" if objective.status != "active" else "completed")
        try:
            ApiObjectiveRepository(str(incident_id)).set_status(objective.id, next_status)
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Quick Status", f"Failed to update status:\n{exc}")
            return
        self.reload()

    def _duplicate_objective(self, proxy_index: QModelIndex) -> None:
        source_index = self._proxy.mapToSource(proxy_index)
        objective = self._model.objective_for_row(source_index.row())
        if not objective:
            return
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            return
        try:
            ApiObjectiveRepository(str(incident_id)).create_objective(
                {
                    "text": f"{objective.text} (Copy)",
                    "priority": objective.priority,
                    "status": "draft",
                    "owner_section": objective.owner_section,
                    "op_period_id": objective.op_period_id,
                    "tags": list(objective.tags),
                }
            )
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Duplicate Objective", f"Failed to duplicate objective:\n{exc}")
            return
        self.reload()

    def _persist_reorder(self, ordered_ids: List[str]) -> None:
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            return
        try:
            ApiObjectiveRepository(str(incident_id)).reorder_objectives(ordered_ids)
        except Exception as exc:  # pragma: no cover
            QMessageBox.warning(self, "Reorder", f"Failed to persist order:\n{exc}")
