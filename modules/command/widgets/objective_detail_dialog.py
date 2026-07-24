from __future__ import annotations

"""Modeless editor dialog for incident objectives."""

import re
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.command.models.objectives import (
    ApiObjectiveRepository,
    PRIORITY_VALUES,
    STATUS_VALUES,
    ObjectiveDetail,
)
from utils import incident_context
from utils.styles import get_palette, subscribe_theme

PRIORITY_COLORS = {
    "low": "#546e7a",
    "normal": "#1565c0",
    "high": "#e65100",
    "urgent": "#c62828",
}

STATUS_COLORS = {
    "draft": "#757575",
    "active": "#2e7d32",
    "deferred": "#f9a825",
    "completed": "#1565c0",
    "cancelled": "#616161",
}


def _badge(text: str, color: str) -> QLabel:
    label = QLabel(text)
    label.setAlignment(Qt.AlignCenter)
    label.setFixedHeight(24)
    label.setStyleSheet(
        f"border-radius: 12px; padding: 2px 12px; color: white; "
        f"background: {color}; font-weight: 600;"
    )
    return label


class ObjectiveDetailDialog(QDialog):
    """Qt Widgets dialog that keeps focus on strategic outcomes."""

    def __init__(self, parent: Optional[QWidget] = None, on_saved: Optional[Callable[[], None]] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setModal(False)
        self.setWindowTitle("Objective Detail")
        self.setMinimumSize(680, 560)
        self._objective_id: Optional[str] = None
        self._detail: Optional[ObjectiveDetail] = None
        self._on_saved = on_saved
        self._detail_windows: list = []
        self._field_labels: list = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        layout.addWidget(self._build_header())
        layout.addWidget(self._build_action_bar())

        self._tab_widget = QTabWidget(self)
        layout.addWidget(self._tab_widget, 1)

        self._build_overview_tab()
        self._build_tasks_tab()
        self._build_narrative_tab()
        self._build_log_tab()

        self._apply_styles()
        subscribe_theme(self, lambda *_: self._apply_styles())

        self.adjustSize()

    # ------------------------------------------------------------------
    def _apply_styles(self) -> None:
        pal = get_palette()
        fg_muted = pal.get("fg_muted", pal["muted"]).name()
        for label in self._field_labels:
            label.setStyleSheet(f"color: {fg_muted}; font-weight: 600;")
        self._updated_label.setStyleSheet(f"color: {fg_muted};")

    # ------------------------------------------------------------------
    def load_objective(self, objective_id: str) -> None:
        self._objective_id = objective_id
        self._refresh()

    # ------------------------------------------------------------------
    def _build_header(self) -> QWidget:
        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setStyleSheet(
            "QFrame { background: palette(base); border: 1px solid palette(mid); border-radius: 6px; }"
        )
        outer = QVBoxLayout(card)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        self._code_label = QLabel("OBJ-")
        code_font = QFont()
        code_font.setBold(True)
        code_font.setPointSize(code_font.pointSize() + 2)
        self._code_label.setFont(code_font)
        title_row.addWidget(self._code_label)

        self._priority_badge = _badge("Normal", PRIORITY_COLORS["normal"])
        self._status_badge = _badge("Draft", STATUS_COLORS["draft"])
        title_row.addWidget(self._priority_badge)
        title_row.addWidget(self._status_badge)
        title_row.addStretch(1)

        self._updated_label = QLabel("–")
        title_row.addWidget(self._updated_label)
        outer.addLayout(title_row)

        self._objective_text = QTextEdit()
        self._objective_text.setPlaceholderText("Objective statement")
        self._objective_text.setAcceptRichText(False)
        self._objective_text.setFixedHeight(72)
        outer.addWidget(self._objective_text)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        self._priority_combo = QComboBox()
        self._priority_combo.addItems([p.title() for p in PRIORITY_VALUES])
        self._priority_combo.currentTextChanged.connect(self._on_priority_changed)

        self._status_combo = QComboBox()
        self._status_combo.addItems([s.title() for s in STATUS_VALUES])
        self._status_combo.currentTextChanged.connect(self._on_status_changed)

        self._owner_edit = QLineEdit()
        self._owner_edit.setPlaceholderText("Owner or Section")

        self._tags_edit = QLineEdit()
        self._tags_edit.setPlaceholderText("Tags (comma separated)")

        self._op_label = QLabel("–")

        grid.addWidget(self._field_label("Priority"), 0, 0)
        grid.addWidget(self._priority_combo, 0, 1)
        grid.addWidget(self._field_label("Status"), 0, 2)
        grid.addWidget(self._status_combo, 0, 3)

        grid.addWidget(self._field_label("Owner/Section"), 1, 0)
        grid.addWidget(self._owner_edit, 1, 1)
        grid.addWidget(self._field_label("Operational Period"), 1, 2)
        grid.addWidget(self._op_label, 1, 3)

        grid.addWidget(self._field_label("Tags"), 2, 0)
        grid.addWidget(self._tags_edit, 2, 1, 1, 3)

        outer.addLayout(grid)
        return card

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        self._field_labels.append(label)
        return label

    def _build_action_bar(self) -> QWidget:
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self._save_button = QPushButton("Save")
        self._save_button.setDefault(True)
        self._save_button.clicked.connect(self._save)

        self._create_task_button = QPushButton("Create Task")
        self._create_task_button.clicked.connect(self._create_task)

        self._history_button = QPushButton("History")
        self._history_button.clicked.connect(self._show_history)

        self._snippet_button = QPushButton("ICS-202 Snippet")
        self._snippet_button.clicked.connect(self._show_snippet)

        row.addWidget(self._save_button)
        row.addWidget(self._create_task_button)
        row.addWidget(self._history_button)
        row.addWidget(self._snippet_button)
        row.addStretch(1)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row.addWidget(spacer)
        return bar

    def _build_overview_tab(self) -> None:
        """Read-only roll-up of the ICS-204 work assignments ("strategies")
        linked to this objective. Strategies themselves are authored and
        managed in the Tactics & Resource Planner — this tab is a command
        view into that work, not a second place to edit it.
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        self._strategies_table = QTableWidget(0, 5, tab)
        self._strategies_table.setHorizontalHeaderLabels(
            ["Assignment #", "Name", "Branch/Division", "Planning Status", "Tasks"]
        )
        self._strategies_table.horizontalHeader().setStretchLastSection(True)
        self._strategies_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._strategies_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._strategies_table.setAlternatingRowColors(True)
        self._strategies_table.doubleClicked.connect(lambda _: self._open_selected_work_assignment())

        layout.addWidget(self._strategies_table)

        button_bar = QHBoxLayout()
        open_btn = QPushButton("Open Strategy")
        open_btn.clicked.connect(self._open_selected_work_assignment)
        planner_btn = QPushButton("Open Tactics & Resource Planner")
        planner_btn.clicked.connect(self._open_planner)
        button_bar.addWidget(open_btn)
        button_bar.addWidget(planner_btn)
        button_bar.addStretch(1)
        layout.addLayout(button_bar)

        self._tab_widget.addTab(tab, "Overview")

    def _build_tasks_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)

        self._tasks_table = QTableWidget(0, 6, tab)
        self._tasks_table.setHorizontalHeaderLabels(
            ["Task", "Title", "Assignee/Team", "Status", "Due", "Open"]
        )
        self._tasks_table.horizontalHeader().setStretchLastSection(True)
        self._tasks_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._tasks_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tasks_table.setAlternatingRowColors(True)
        layout.addWidget(self._tasks_table)

        button_bar = QHBoxLayout()
        new_task_btn = QPushButton("New Task")
        new_task_btn.clicked.connect(self._create_task)
        unlink_btn = QPushButton("Unlink")
        unlink_btn.clicked.connect(self._unlink_task)
        button_bar.addWidget(new_task_btn)
        button_bar.addWidget(unlink_btn)
        button_bar.addStretch(1)
        layout.addLayout(button_bar)

        self._tab_widget.addTab(tab, "Tasks")

    def _build_narrative_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        self._narrative_edit = QPlainTextEdit()
        self._narrative_edit.setPlaceholderText("Narrative notes for this objective")
        layout.addWidget(self._narrative_edit)
        self._tab_widget.addTab(tab, "Narrative")

    def _build_log_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        self._log_list = QListWidget()
        layout.addWidget(self._log_list)
        self._tab_widget.addTab(tab, "Log")

    # ------------------------------------------------------------------
    def _on_priority_changed(self, text: str) -> None:
        color = PRIORITY_COLORS.get(text.lower(), PRIORITY_COLORS["normal"])
        self._priority_badge.setText(text)
        self._priority_badge.setStyleSheet(
            f"border-radius: 12px; padding: 2px 12px; color: white; background: {color}; font-weight: 600;"
        )

    def _on_status_changed(self, text: str) -> None:
        color = STATUS_COLORS.get(text.lower(), STATUS_COLORS["draft"])
        self._status_badge.setText(text)
        self._status_badge.setStyleSheet(
            f"border-radius: 12px; padding: 2px 12px; color: white; background: {color}; font-weight: 600;"
        )

    # ------------------------------------------------------------------
    def _refresh(self) -> None:
        incident_id = incident_context.get_active_incident_id()
        if not incident_id or self._objective_id is None:
            return
        try:
            repository = ApiObjectiveRepository(str(incident_id))
            detail = repository.get_objective_detail(self._objective_id)
            history = repository.list_history(self._objective_id)
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Objective Detail", f"Failed to load objective:\n{exc}")
            return
        self._detail = detail
        summary = detail.summary
        self._code_label.setText(summary.code)
        self._objective_text.setPlainText(summary.text)
        priority_index = PRIORITY_VALUES.index(summary.priority) if summary.priority in PRIORITY_VALUES else 0
        self._priority_combo.setCurrentIndex(priority_index)
        status_index = STATUS_VALUES.index(summary.status) if summary.status in STATUS_VALUES else 0
        self._status_combo.setCurrentIndex(status_index)
        self._owner_edit.setText(summary.owner_section or "")
        self._tags_edit.setText(", ".join(summary.tags))
        self._op_label.setText(str(summary.op_period_id or "–"))
        updated_by = summary.updated_by or "Unknown"
        updated_ts = summary.updated_at.isoformat(sep=" ", timespec="seconds") if summary.updated_at else ""
        self._updated_label.setText(f"Updated {updated_ts} by {updated_by}" if updated_ts else "–")
        self._narrative_edit.setPlainText(self._detail.narrative or "")
        self._populate_overview()
        self._populate_tasks()
        self._populate_history(history)

    def _objective_numeric_id(self) -> Optional[int]:
        """Best-effort numeric id parsed from the objective code (e.g. 'OBJ-7' -> 7),
        used to look up work assignments tagged with this objective."""
        if not self._detail:
            return None
        match = re.search(r"(\d+)$", self._detail.summary.code or "")
        return int(match.group(1)) if match else None

    def _populate_overview(self) -> None:
        self._strategies_table.setRowCount(0)
        objective_num = self._objective_numeric_id()
        if objective_num is None:
            return
        from modules.planning.tactics_resources.data.work_assignment_repository import (
            WorkAssignmentRepository,
        )
        repo = WorkAssignmentRepository()
        try:
            assignments = repo.list_work_assignments(
                {"objective_id": objective_num, "show_archived": False}
            )
        except Exception:
            assignments = []
        for wa in assignments:
            row = self._strategies_table.rowCount()
            self._strategies_table.insertRow(row)
            self._strategies_table.setItem(row, 0, QTableWidgetItem(wa.assignment_number))
            self._strategies_table.setItem(row, 1, QTableWidgetItem(wa.assignment_name))
            branch_div = " / ".join(p for p in (wa.branch, wa.division_group) if p)
            self._strategies_table.setItem(row, 2, QTableWidgetItem(branch_div))
            self._strategies_table.setItem(row, 3, QTableWidgetItem(wa.planning_status))
            try:
                task_count = len(repo.list_linked_tasks(wa.id))
            except Exception:
                task_count = 0
            self._strategies_table.setItem(row, 4, QTableWidgetItem(str(task_count)))
            self._strategies_table.item(row, 0).setData(Qt.UserRole, wa.id)

    def _open_selected_work_assignment(self) -> None:
        row = self._strategies_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Open Strategy", "Select a strategy row first.")
            return
        item = self._strategies_table.item(row, 0)
        wa_id = item.data(Qt.UserRole) if item else None
        if wa_id is None:
            return
        from modules.planning.tactics_resources import open_tactics_resources_planner
        open_tactics_resources_planner(parent=self)

    def _open_planner(self) -> None:
        from modules.planning.tactics_resources import open_tactics_resources_planner
        open_tactics_resources_planner(parent=self)

    def _populate_tasks(self) -> None:
        self._tasks_table.setRowCount(0)
        if not self._detail:
            return
        for task in self._detail.tasks:
            row = self._tasks_table.rowCount()
            self._tasks_table.insertRow(row)
            self._tasks_table.setItem(row, 0, QTableWidgetItem(task.task_number))
            self._tasks_table.setItem(row, 1, QTableWidgetItem(task.title))
            self._tasks_table.setItem(row, 2, QTableWidgetItem(task.assignee or ""))
            self._tasks_table.setItem(row, 3, QTableWidgetItem(task.status))
            self._tasks_table.setItem(row, 4, QTableWidgetItem(task.due or ""))
            self._tasks_table.setItem(row, 5, QTableWidgetItem("Yes" if task.is_open else "No"))
            self._tasks_table.item(row, 0).setData(Qt.UserRole, (task.link_id, task.task_db_id))

    def _populate_history(self, history) -> None:
        self._log_list.clear()
        for entry in history:
            label = f"{entry.ts} – {entry.action}"
            if entry.field:
                label += f" ({entry.field}: {entry.old_value or ''} → {entry.new_value or ''})"
            item = QListWidgetItem(label)
            self._log_list.addItem(item)

    # ------------------------------------------------------------------
    def _save(self) -> None:
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            QMessageBox.warning(self, "Save", "Select an incident before saving objectives.")
            return
        payload = {
            "text": self._objective_text.toPlainText().strip(),
            "priority": self._priority_combo.currentText().lower(),
            "status": self._status_combo.currentText().lower(),
            "owner_section": self._owner_edit.text().strip() or None,
            "tags": [tag.strip() for tag in self._tags_edit.text().split(",") if tag.strip()],
            "narrative": self._narrative_edit.toPlainText().strip() or None,
        }
        try:
            repository = ApiObjectiveRepository(str(incident_id))
            if self._objective_id is None:
                detail = repository.create_objective(payload)
            else:
                detail = repository.update_objective(self._objective_id, payload)
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Save", f"Failed to save objective:\n{exc}")
            return
        self._objective_id = detail.summary.id
        self._detail = detail
        QMessageBox.information(self, "Save", "Objective saved.")
        self._refresh()
        if self._on_saved:
            self._on_saved()

    def _create_task(self) -> None:
        if self._objective_id is None:
            QMessageBox.warning(self, "Create Task", "Save the objective before creating tasks.")
            return
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            return
        try:
            from modules.operations.taskings.repository import create_task
            new_id = create_task(title="<New Task>")
            ApiObjectiveRepository(str(incident_id)).link_task(self._objective_id, new_id)
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Create Task", f"Failed to create task:\n{exc}")
            return
        self._refresh()
        try:
            from modules.operations.taskings.windows import open_task_detail_window
            open_task_detail_window(new_id)
        except Exception:
            pass

    def _unlink_task(self) -> None:
        row = self._tasks_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Unlink Task", "Select a task to unlink.")
            return
        item = self._tasks_table.item(row, 0)
        data = item.data(Qt.UserRole) if item else None
        if not data:
            return
        link_id, _task_id = data
        incident_id = incident_context.get_active_incident_id()
        if not incident_id or self._objective_id is None:
            return
        if QMessageBox.question(
            self, "Unlink Task", "Remove this task's link to the objective?"
        ) != QMessageBox.Yes:
            return
        try:
            ApiObjectiveRepository(str(incident_id)).unlink_task(self._objective_id, link_id)
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Unlink Task", f"Failed to unlink task:\n{exc}")
            return
        self._refresh()

    def _show_history(self) -> None:
        self._tab_widget.setCurrentIndex(3)

    def _show_snippet(self) -> None:
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            QMessageBox.warning(self, "ICS-202", "Select an incident to export ICS-202 data.")
            return
        if not self._detail:
            QMessageBox.warning(self, "ICS-202", "Save the objective first.")
            return
        try:
            payload = ApiObjectiveRepository(str(incident_id)).export_ics202()
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "ICS-202", f"Failed to build ICS-202 export:\n{exc}")
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
            QMessageBox.information(self, "ICS-202", f"ICS-202 exported to:\n{result.path}")
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "ICS-202", f"Export failed:\n{exc}")

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        super().closeEvent(event)
        self._detail = None
