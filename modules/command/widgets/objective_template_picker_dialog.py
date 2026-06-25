from __future__ import annotations

"""Modal picker for importing master Objective Templates — and their
suggested Strategy Templates — into an incident."""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules.command.models.objectives import ApiObjectiveRepository
from modules.planning.models.objectives_dao import ObjectivesDAO, ObjectiveTemplate
from modules.planning.models.strategy_templates_dao import StrategyTemplate, StrategyTemplatesDAO
from utils import incident_context


class ObjectiveTemplatePickerDialog(QDialog):
    """Lets the user import one or more master Objective Templates as new
    incident objectives, optionally along with their suggested Strategy
    Templates (ICS-204 work assignments). Template authoring/maintenance
    happens in the Objective/Strategy Templates editors (reachable from
    here, and from Edit > Objectives) — this dialog only consumes the
    library, it doesn't duplicate the editing surface.
    """

    def __init__(self, parent: Optional[QWidget] = None, on_imported=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Objective From Template")
        self.setModal(True)
        self.setMinimumSize(880, 480)
        self._objectives_dao = ObjectivesDAO()
        self._strategies_dao = StrategyTemplatesDAO()
        self._templates: list[ObjectiveTemplate] = []
        self._suggested_strategies: list[StrategyTemplate] = []
        self._on_imported = on_imported

        outer = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal, self)
        outer.addWidget(splitter, 1)

        # Left: objective templates
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        search_row = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search objective templates…")
        self._search_edit.textChanged.connect(self._reload)
        search_row.addWidget(self._search_edit)
        manage_btn = QPushButton("Manage Objective Templates…")
        manage_btn.clicked.connect(self._open_objective_manager)
        search_row.addWidget(manage_btn)
        left_layout.addLayout(search_row)

        self._table = QTableWidget(0, 4, self)
        self._table.setHorizontalHeaderLabels(["Code", "Title", "Default Section", "Priority"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.itemSelectionChanged.connect(self._on_objective_selection_changed)
        self._table.doubleClicked.connect(lambda _: self._import_selected())
        left_layout.addWidget(self._table)
        splitter.addWidget(left)

        # Right: suggested strategy templates for the selected objective
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        strategies_header = QHBoxLayout()
        strategies_header.addWidget(QLabel("Suggested Strategies"))
        strategies_header.addStretch(1)
        manage_strategies_btn = QPushButton("Manage Strategy Templates…")
        manage_strategies_btn.clicked.connect(self._open_strategy_manager)
        strategies_header.addWidget(manage_strategies_btn)
        right_layout.addLayout(strategies_header)

        self._strategies_hint = QLabel(
            "Select a single objective template to see its suggested strategies."
        )
        self._strategies_hint.setWordWrap(True)
        self._strategies_hint.setStyleSheet("color: palette(mid);")
        right_layout.addWidget(self._strategies_hint)

        self._strategies_list = QListWidget()
        right_layout.addWidget(self._strategies_list)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        button_row = QHBoxLayout()
        import_btn = QPushButton("Import Selected")
        import_btn.setDefault(True)
        import_btn.clicked.connect(self._import_selected)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_row.addStretch(1)
        button_row.addWidget(import_btn)
        button_row.addWidget(close_btn)
        outer.addLayout(button_row)

        self._reload()

    # ------------------------------------------------------------------
    def _reload(self) -> None:
        search = self._search_edit.text().strip() or None
        try:
            self._templates = self._objectives_dao.list_templates(search=search, include_archived=False)
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Objective Templates", f"Failed to load templates:\n{exc}")
            self._templates = []
        self._table.setRowCount(0)
        for template in self._templates:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(template.code or ""))
            self._table.setItem(row, 1, QTableWidgetItem(template.title))
            self._table.setItem(row, 2, QTableWidgetItem(template.default_section or ""))
            self._table.setItem(row, 3, QTableWidgetItem(template.priority))
            self._table.item(row, 0).setData(Qt.UserRole, template.id)
        self._refresh_suggested_strategies()

    def _selected_objective_templates(self) -> list[ObjectiveTemplate]:
        rows = sorted({idx.row() for idx in self._table.selectionModel().selectedRows()})
        result = []
        for row in rows:
            item = self._table.item(row, 0)
            template_id = item.data(Qt.UserRole) if item else None
            template = next((t for t in self._templates if t.id == template_id), None)
            if template is not None:
                result.append(template)
        return result

    def _on_objective_selection_changed(self) -> None:
        self._refresh_suggested_strategies()

    def _refresh_suggested_strategies(self) -> None:
        self._strategies_list.clear()
        selected = self._selected_objective_templates()
        if len(selected) != 1:
            self._strategies_hint.setText(
                "Select a single objective template to see its suggested strategies."
            )
            self._strategies_hint.setVisible(True)
            self._suggested_strategies = []
            return
        objective_template = selected[0]
        try:
            self._suggested_strategies = self._strategies_dao.list_templates(
                objective_template_id=objective_template.id, include_archived=False
            )
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Strategy Templates", f"Failed to load suggested strategies:\n{exc}")
            self._suggested_strategies = []
        if not self._suggested_strategies:
            self._strategies_hint.setText("No suggested strategies for this objective template.")
            self._strategies_hint.setVisible(True)
            return
        self._strategies_hint.setVisible(False)
        for strategy in self._suggested_strategies:
            item = QListWidgetItem(f"{strategy.title} ({strategy.assignment_kind}, {strategy.priority})")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            item.setData(Qt.UserRole, strategy.id)
            self._strategies_list.addItem(item)

    def _checked_strategy_ids(self) -> set[int]:
        ids: set[int] = set()
        for i in range(self._strategies_list.count()):
            item = self._strategies_list.item(i)
            if item.checkState() == Qt.Checked:
                ids.add(item.data(Qt.UserRole))
        return ids

    def _open_objective_manager(self) -> None:
        from modules.planning.widgets.objectives_editor import show_objectives_editor
        editor = show_objectives_editor(None)
        editor.window_closed.connect(self._reload)
        editor.raise_()
        editor.activateWindow()

    def _open_strategy_manager(self) -> None:
        from modules.planning.widgets.strategy_templates_editor import show_strategy_templates_editor
        editor = show_strategy_templates_editor()
        editor.window_closed.connect(self._refresh_suggested_strategies)
        editor.raise_()
        editor.activateWindow()

    # ------------------------------------------------------------------
    def _import_selected(self) -> None:
        objective_templates = self._selected_objective_templates()
        if not objective_templates:
            QMessageBox.information(self, "Import Template", "Select one or more objective templates to import.")
            return
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            QMessageBox.warning(self, "Import Template", "Select an incident before importing objectives.")
            return

        checked_strategy_ids = self._checked_strategy_ids() if len(objective_templates) == 1 else set()
        repo = ApiObjectiveRepository(str(incident_id))
        imported_objectives, failed_objectives = 0, 0
        imported_strategies, failed_strategies = 0, 0

        for template in objective_templates:
            payload = {
                "text": template.title,
                "priority": template.priority.lower(),
                "status": "draft",
                "owner_section": template.default_section,
                "tags": list(template.tags or []),
                "narrative": template.description or None,
            }
            try:
                detail = repo.create_objective(payload)
                imported_objectives += 1
            except Exception:
                failed_objectives += 1
                continue
            if checked_strategy_ids:
                objective_num = self._numeric_suffix(detail.summary.code)
                imported_strategies, failed_strategies = self._import_strategies(
                    checked_strategy_ids, objective_num, imported_strategies, failed_strategies
                )

        if imported_objectives and self._on_imported:
            self._on_imported()

        summary = f"Imported {imported_objectives} objective(s)."
        if checked_strategy_ids:
            summary += f" Imported {imported_strategies} strategy(ies)."
        if failed_objectives or failed_strategies:
            summary += f" ({failed_objectives} objective + {failed_strategies} strategy failure(s).)"
            QMessageBox.warning(self, "Import Template", summary)
        else:
            QMessageBox.information(self, "Import Template", summary)
        if imported_objectives:
            self.accept()

    def _import_strategies(
        self,
        strategy_ids: set[int],
        objective_num: Optional[int],
        imported: int,
        failed: int,
    ) -> tuple[int, int]:
        from modules.planning.tactics_resources.data.work_assignment_repository import (
            WorkAssignmentRepository,
        )
        wa_repo = WorkAssignmentRepository()
        for strategy_id in strategy_ids:
            strategy = next((s for s in self._suggested_strategies if s.id == strategy_id), None)
            if strategy is None:
                continue
            data = {
                "assignment_name": strategy.title,
                "objective_id": objective_num,
                "branch": strategy.branch or "",
                "division_group": strategy.division_group or "",
                "assignment_kind": strategy.assignment_kind,
                "priority": strategy.priority,
                "description": strategy.description,
            }
            try:
                wa_repo.create_work_assignment(data)
                imported += 1
            except Exception:
                failed += 1
        return imported, failed

    @staticmethod
    def _numeric_suffix(code: Optional[str]) -> Optional[int]:
        import re
        if not code:
            return None
        match = re.search(r"(\d+)$", code)
        return int(match.group(1)) if match else None
