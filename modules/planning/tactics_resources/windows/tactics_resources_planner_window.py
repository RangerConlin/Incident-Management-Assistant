"""
TacticsResourcesPlannerWindow
=============================
Main board window for the Tactics and Resources Planner.

Shows all Work Assignments in a filterable table.
Double-click (or press Enter) to open the Work Assignment Detail Window.

Accessible from: Planning, Operations, and Logistics menus.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QSortFilterProxyModel, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QSplitter,
    QTableView,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from modules.planning.tactics_resources.data.hazard_prefill_service import HazardPrefillService
from modules.planning.tactics_resources.data.resource_gap_service import ResourceGapService
from modules.planning.tactics_resources.data.work_assignment_repository import WorkAssignmentRepository
from modules.planning.tactics_resources.models.work_assignment_models import (
    PLANNING_STATUS_VALUES,
    RESOURCE_STATUS_VALUES,
    SAFETY_STATUS_VALUES,
    WorkAssignment,
)
from modules.planning.tactics_resources.windows.work_assignment_detail_window import (
    WorkAssignmentDetailWindow,
)


# ---------------------------------------------------------------------------
# Table model
# ---------------------------------------------------------------------------

_COLUMNS = [
    "Strategy #",
    "Name",
    "Objective",
    "OP",
    "Branch",
    "Division / Group",
    "Planning Status",
    "Resource Status",
    "Req. Resources",
    "Assigned",
    "Gap",
    "Hazards",
    "Open Hazards",
    "Safety Status",
    "Linked Tasks",
    "Updated At",
]


class WorkAssignmentTableModel(QAbstractTableModel):
    """Qt table model for the list of Work Assignments."""

    def __init__(self) -> None:
        super().__init__()
        self._rows: list[WorkAssignment] = []
        # Extended data per row: (req_total, assigned_total, gap, hazard_total, open_hazards, task_count)
        self._meta: list[tuple[int, int, int, int, int, int]] = []

    def set_data(
        self,
        rows: list[WorkAssignment],
        meta: list[tuple[int, int, int, int, int, int]],
    ) -> None:
        self.beginResetModel()
        self._rows = rows
        self._meta = meta
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return 0 if parent.isValid() else len(_COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> object:  # type: ignore[override]
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal and 0 <= section < len(_COLUMNS):
            return _COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> object:  # type: ignore[override]
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        if row >= len(self._rows):
            return None
        wa = self._rows[row]
        meta = self._meta[row] if row < len(self._meta) else (0, 0, 0, 0, 0, 0)
        req_total, assigned_total, gap, hazard_total, open_hazards, task_count = meta

        if role == Qt.DisplayRole:
            mapping = [
                wa.assignment_number,
                wa.assignment_name,
                str(wa.objective_id or ""),
                str(wa.operational_period_id or ""),
                wa.branch,
                wa.division_group,
                wa.planning_status,
                wa.resource_status,
                str(req_total),
                str(assigned_total),
                str(gap),
                str(hazard_total),
                str(open_hazards),
                wa.safety_status,
                str(task_count),
                wa.updated_at,
            ]
            if 0 <= col < len(mapping):
                return mapping[col]

        if role == Qt.UserRole:
            return wa.id

        # Highlight gap or open hazards in red
        if role == Qt.ForegroundRole:
            from PySide6.QtGui import QColor
            if col == 12 and gap > 0:       # Gap column
                return QColor("red")
            if col == 14 and open_hazards > 0:  # Open Hazards column
                return QColor("darkRed")

        return None

    def assignment_for_row(self, row: int) -> WorkAssignment | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None


# ---------------------------------------------------------------------------
# Proxy model (search)
# ---------------------------------------------------------------------------

class _FilterProxy(QSortFilterProxyModel):
    def __init__(self) -> None:
        super().__init__()
        self._search = ""

    def set_search(self, text: str) -> None:
        self._search = text.lower().strip()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # type: ignore[override]
        if not self._search:
            return True
        model = self.sourceModel()
        if model is None:
            return True
        for col in (0, 1, 4, 5):
            idx = model.index(source_row, col, source_parent)
            text = str(model.data(idx, Qt.DisplayRole) or "").lower()
            if self._search in text:
                return True
        return False


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class TacticsResourcesPlannerWindow(QWidget):
    """
    Main planning board for Work Assignments.

    Designed to be opened modeless (non-blocking).
    """

    def __init__(self, db_path: str | None = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tactics and Resources Planner")
        self.setWindowFlags(Qt.Window)
        self.setMinimumSize(1100, 650)
        self._db_path = db_path
        self._gap_service = ResourceGapService(db_path)
        self._hazard_service = HazardPrefillService()
        self._open_detail_windows: list[WorkAssignmentDetailWindow] = []

        self._build_ui()
        self.reload()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Create model and proxy first — the filter bar wires signals to them
        self._model = WorkAssignmentTableModel()
        self._proxy = _FilterProxy()
        self._proxy.setSourceModel(self._model)

        # Filter bar
        layout.addWidget(self._build_filter_bar())

        # Toolbar
        layout.addWidget(self._build_toolbar())

        # Splitter: table on top, preview pane below
        splitter = QSplitter(Qt.Vertical)

        # Table

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.horizontalHeader().setSectionsMovable(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.doubleClicked.connect(self._on_double_click)
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        splitter.addWidget(self._table)

        # Preview pane
        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setMaximumHeight(180)
        self._preview.setPlaceholderText("Select a strategy to see a summary.")
        splitter.addWidget(self._preview)
        splitter.setSizes([450, 180])

        layout.addWidget(splitter, 1)

    def _build_filter_bar(self) -> QWidget:
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search strategies…")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.setMaximumWidth(220)
        self._search_edit.textChanged.connect(self._proxy.set_search)
        row.addWidget(QLabel("Search:"))
        row.addWidget(self._search_edit)

        def _combo(placeholder: str, values: list[str]) -> QComboBox:
            c = QComboBox()
            c.addItem(placeholder)
            c.addItems(values)
            c.currentIndexChanged.connect(self.reload)
            return c

        self._filter_status = _combo("All Statuses", PLANNING_STATUS_VALUES)
        self._filter_safety = _combo("All Safety", SAFETY_STATUS_VALUES)
        self._filter_resource = _combo("All Resources", RESOURCE_STATUS_VALUES)

        row.addWidget(QLabel("Status:"))
        row.addWidget(self._filter_status)
        row.addWidget(QLabel("Safety:"))
        row.addWidget(self._filter_safety)
        row.addWidget(QLabel("Resource:"))
        row.addWidget(self._filter_resource)

        self._show_archived = QCheckBox("Show Archived")
        self._show_archived.stateChanged.connect(self.reload)
        row.addWidget(self._show_archived)

        row.addStretch(1)
        return bar

    def _build_toolbar(self) -> QToolBar:
        tb = QToolBar("Planner")
        tb.setMovable(False)

        def _action(label: str, slot) -> QAction:
            act = QAction(label, self)
            act.triggered.connect(slot)
            tb.addAction(act)
            return act

        _action("New Strategy", self._new_assignment)
        _action("Edit / Open", self._open_selected)
        _action("Clone", self._clone_selected)
        tb.addSeparator()
        _action("Archive", self._archive_selected)
        _action("Restore", self._restore_selected)
        tb.addSeparator()
        _action("Recalculate Gaps", self._recalculate_selected)
        _action("Apply Default Hazards", self._apply_hazards_selected)
        tb.addSeparator()
        _action("Create Task", self._create_task_selected)
        _action("Link Task", self._link_task_selected)
        tb.addSeparator()
        _action("Refresh", self.reload)
        return tb

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def reload(self) -> None:
        """Reload the table from the database."""
        filters: dict = {}
        if self._show_archived.isChecked():
            filters["show_archived"] = True
        status = self._filter_status.currentText()
        if status and status != self._filter_status.itemText(0):
            filters["planning_status"] = status
        safety = self._filter_safety.currentText()
        if safety and safety != self._filter_safety.itemText(0):
            filters["safety_status"] = safety
        resource = self._filter_resource.currentText()
        if resource and resource != self._filter_resource.itemText(0):
            filters["resource_status"] = resource

        try:
            repo = WorkAssignmentRepository(self._db_path)
            repo.initialize_schema()
            assignments = repo.list_work_assignments(filters)
        except Exception as exc:
            QMessageBox.critical(self, "Planner", f"Failed to load strategies:\n{exc}")
            return

        meta_list: list[tuple[int, int, int, int, int, int]] = []
        for wa in assignments:
            try:
                reqs = repo.list_resource_requirements(wa.id)
                hazards = repo.list_hazards(wa.id)
                links = repo.list_linked_tasks(wa.id)
            except Exception:
                reqs, hazards, links = [], [], []
            req_total = sum(r.quantity_required for r in reqs)
            assigned_total = sum(r.quantity_assigned for r in reqs)
            gap = sum(max(r.quantity_required - r.quantity_assigned, 0) for r in reqs)
            open_hazards = sum(1 for h in hazards if not h.is_resolved)
            meta_list.append((req_total, assigned_total, gap, len(hazards), open_hazards, len(links)))

        self._model.set_data(assignments, meta_list)
        self._preview.clear()

    # ------------------------------------------------------------------
    # Selection and preview
    # ------------------------------------------------------------------

    def _current_assignment(self) -> WorkAssignment | None:
        indexes = self._table.selectedIndexes()
        if not indexes:
            return None
        source_row = self._proxy.mapToSource(indexes[0]).row()
        return self._model.assignment_for_row(source_row)

    def _on_selection_changed(self) -> None:
        wa = self._current_assignment()
        if wa is None:
            self._preview.clear()
            return
        try:
            summary = self._gap_service.summarize_assignment_resources(wa.id)
        except Exception:
            summary = "(resource summary unavailable)"
        lines = [
            f"<b>{wa.assignment_number} {wa.assignment_name}</b>",
            f"Status: {wa.planning_status} | Safety: {wa.safety_status} | Resources: {wa.resource_status}",
            f"Branch: {wa.branch} | Division/Group: {wa.division_group}",
            "",
            f"<b>Description:</b> {wa.description or '(none)'}",
            f"<b>Tactics:</b> {wa.tactics_summary or '(none)'}",
            "",
            f"<b>Resources:</b><pre>{summary}</pre>",
        ]
        self._preview.setHtml("<br>".join(lines))

    # ------------------------------------------------------------------
    # Toolbar and context menu actions
    # ------------------------------------------------------------------

    def _new_assignment(self) -> None:
        win = WorkAssignmentDetailWindow(db_path=self._db_path, parent=None)
        win.saved.connect(self.reload)
        win.show()
        self._open_detail_windows.append(win)

    def _open_selected(self) -> None:
        wa = self._current_assignment()
        if wa is None:
            QMessageBox.information(self, "Open", "Select a strategy first.")
            return
        self._open_detail(wa.id)

    def _open_detail(self, work_assignment_id: int) -> None:
        # Raise existing window if already open
        for win in self._open_detail_windows:
            if not win.isVisible():
                self._open_detail_windows.remove(win)
                break
            if win._work_assignment_id == work_assignment_id:
                win.raise_()
                win.activateWindow()
                return
        win = WorkAssignmentDetailWindow(
            work_assignment_id=work_assignment_id, db_path=self._db_path, parent=None
        )
        win.saved.connect(self.reload)
        win.show()
        self._open_detail_windows.append(win)

    def _on_double_click(self, index: QModelIndex) -> None:
        wa = self._current_assignment()
        if wa and wa.id:
            self._open_detail(wa.id)

    def _clone_selected(self) -> None:
        wa = self._current_assignment()
        if wa is None:
            QMessageBox.information(self, "Clone", "Select a strategy to clone.")
            return
        try:
            repo = WorkAssignmentRepository(self._db_path)
            new_id = repo.clone_work_assignment(wa.id)
        except Exception as exc:
            QMessageBox.critical(self, "Clone", f"Failed to clone:\n{exc}")
            return
        self.reload()
        if new_id:
            self._open_detail(new_id)

    def _archive_selected(self) -> None:
        wa = self._current_assignment()
        if wa is None:
            return
        if wa.is_archived:
            QMessageBox.information(self, "Archive", "Assignment is already archived.")
            return
        if QMessageBox.question(
            self, "Archive", f"Archive '{wa.assignment_name}'?"
        ) != QMessageBox.Yes:
            return
        try:
            repo = WorkAssignmentRepository(self._db_path)
            repo.archive_work_assignment(wa.id)
        except Exception as exc:
            QMessageBox.critical(self, "Archive", f"Failed:\n{exc}")
            return
        self.reload()

    def _restore_selected(self) -> None:
        wa = self._current_assignment()
        if wa is None:
            return
        if not wa.is_archived:
            QMessageBox.information(self, "Restore", "Assignment is not archived.")
            return
        try:
            repo = WorkAssignmentRepository(self._db_path)
            repo.restore_work_assignment(wa.id)
        except Exception as exc:
            QMessageBox.critical(self, "Restore", f"Failed:\n{exc}")
            return
        self.reload()

    def _recalculate_selected(self) -> None:
        wa = self._current_assignment()
        if wa is None:
            QMessageBox.information(self, "Recalculate", "Select a strategy first.")
            return
        try:
            repo = WorkAssignmentRepository(self._db_path)
            repo.recalculate_all_resource_gaps(wa.id)
        except Exception as exc:
            QMessageBox.critical(self, "Recalculate", f"Failed:\n{exc}")
            return
        self.reload()
        QMessageBox.information(self, "Recalculate", "Resource gaps recalculated.")

    def _apply_hazards_selected(self) -> None:
        wa = self._current_assignment()
        if wa is None:
            QMessageBox.information(self, "Default Hazards", "Select a strategy first.")
            return
        try:
            added, skipped = self._hazard_service.apply_default_hazards(wa.id)
        except Exception as exc:
            QMessageBox.critical(self, "Default Hazards", f"Failed:\n{exc}")
            return
        self.reload()
        QMessageBox.information(
            self, "Default Hazards",
            f"Added {added} hazard(s). Skipped {skipped} (already present or unavailable).",
        )

    def _create_task_selected(self) -> None:
        wa = self._current_assignment()
        if wa is None:
            QMessageBox.information(self, "Create Task", "Select a strategy first.")
            return
        try:
            repo = WorkAssignmentRepository(self._db_path)
            task_id = repo.create_task_from_work_assignment(wa.id)
        except Exception as exc:
            QMessageBox.critical(self, "Create Task", f"Failed:\n{exc}")
            return
        if task_id is None:
            QMessageBox.information(
                self, "Create Task",
                "Taskings module not found — task creation unavailable.\n"
                "Open the strategy and create a task from the Tasks tab.",
            )
        else:
            QMessageBox.information(self, "Create Task", f"Operations task {task_id} created.")
        self.reload()

    def _link_task_selected(self) -> None:
        wa = self._current_assignment()
        if wa is None:
            QMessageBox.information(self, "Link Task", "Select a strategy first.")
            return
        # Open the detail window to the Tasks tab
        self._open_detail(wa.id)

    def _show_context_menu(self, pos) -> None:
        wa = self._current_assignment()
        menu = QMenu(self._table)
        menu.addAction("Open Assignment", self._open_selected)
        menu.addAction("Clone Assignment", self._clone_selected)
        menu.addSeparator()
        if wa and wa.is_archived:
            menu.addAction("Restore", self._restore_selected)
        else:
            menu.addAction("Archive", self._archive_selected)
        menu.addSeparator()
        menu.addAction("Recalculate Resource Gap", self._recalculate_selected)
        menu.addAction("Apply Default Hazards", self._apply_hazards_selected)
        menu.addSeparator()
        menu.addAction("Create Operations Task", self._create_task_selected)
        menu.addAction("Link Existing Task", self._link_task_selected)
        menu.addSeparator()
        copy_action = menu.addAction("Copy Assignment Summary")
        copy_action.triggered.connect(self._copy_summary)
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _copy_summary(self) -> None:
        wa = self._current_assignment()
        if not wa:
            return
        text = (
            f"{wa.assignment_number} {wa.assignment_name}\n"
            f"Status: {wa.planning_status}  Safety: {wa.safety_status}  Resources: {wa.resource_status}\n"
            f"Branch: {wa.branch}  Division/Group: {wa.division_group}"
        )
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
