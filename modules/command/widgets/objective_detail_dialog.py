from __future__ import annotations

"""Modeless editor dialog for incident objectives."""

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
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
    ObjectiveStrategyView,
)
from utils import incident_context

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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        layout.addWidget(self._build_header())
        layout.addWidget(self._build_action_bar())

        self._tab_widget = QTabWidget(self)
        layout.addWidget(self._tab_widget, 1)

        self._build_strategies_tab()
        self._build_tasks_tab()
        self._build_narrative_tab()
        self._build_log_tab()

        self.adjustSize()

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
        self._updated_label.setStyleSheet("color: palette(mid);")
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

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("color: palette(mid); font-weight: 600;")
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

    def _build_strategies_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        self._strategies_table = QTableWidget(0, 5, tab)
        self._strategies_table.setHorizontalHeaderLabels(
            ["Strategy", "Owner", "Status", "Progress", "Open/Total"]
        )
        self._strategies_table.horizontalHeader().setStretchLastSection(True)
        self._strategies_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._strategies_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._strategies_table.setAlternatingRowColors(True)

        layout.addWidget(self._strategies_table)

        button_bar = QHBoxLayout()
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_strategy)
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self._edit_strategy)
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_strategy)
        button_bar.addWidget(add_btn)
        button_bar.addWidget(edit_btn)
        button_bar.addWidget(delete_btn)
        button_bar.addStretch(1)
        layout.addLayout(button_bar)

        self._tab_widget.addTab(tab, "Strategies")

    def _build_tasks_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)

        self._tasks_table = QTableWidget(0, 7, tab)
        self._tasks_table.setHorizontalHeaderLabels(
            ["Task", "Title", "Strategy", "Assignee/Team", "Status", "Due", "Open"]
        )
        self._tasks_table.horizontalHeader().setStretchLastSection(True)
        self._tasks_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._tasks_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tasks_table.setAlternatingRowColors(True)
        layout.addWidget(self._tasks_table)

        button_bar = QHBoxLayout()
        new_task_btn = QPushButton("New Task")
        new_task_btn.clicked.connect(self._create_task)
        button_bar.addWidget(new_task_btn)
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
        self._priority_combo.setCurrentIndex(PRIORITY_VALUES.index(summary.priority))
        self._status_combo.setCurrentIndex(STATUS_VALUES.index(summary.status))
        self._owner_edit.setText(summary.owner_section or "")
        self._tags_edit.setText(", ".join(summary.tags))
        self._op_label.setText(str(summary.op_period_id or "–"))
        updated_by = summary.updated_by or "Unknown"
        updated_ts = summary.updated_at.isoformat(sep=" ", timespec="seconds") if summary.updated_at else ""
        self._updated_label.setText(f"Updated {updated_ts} by {updated_by}" if updated_ts else "–")
        self._narrative_edit.setPlainText(self._detail.narrative or "")
        self._populate_strategies(detail.strategies)
        self._populate_tasks()
        self._populate_history(history)

    def _populate_strategies(self, strategies: list[ObjectiveStrategyView]) -> None:
        self._strategies_table.setRowCount(0)
        for strategy in strategies:
            row = self._strategies_table.rowCount()
            self._strategies_table.insertRow(row)
            self._strategies_table.setItem(row, 0, QTableWidgetItem(strategy.text))
            self._strategies_table.setItem(row, 1, QTableWidgetItem(strategy.owner or ""))
            self._strategies_table.setItem(row, 2, QTableWidgetItem(strategy.status.title()))
            progress = "" if strategy.progress_pct is None else f"{strategy.progress_pct}%"
            self._strategies_table.setItem(row, 3, QTableWidgetItem(progress))
            open_total = f"{strategy.open_tasks}/{strategy.total_tasks}"
            self._strategies_table.setItem(row, 4, QTableWidgetItem(open_total))
            self._strategies_table.item(row, 0).setData(Qt.UserRole, strategy.id)

    def _populate_tasks(self) -> None:
        self._tasks_table.setRowCount(0)
        if not self._detail:
            return
        for task in self._detail.tasks:
            row = self._tasks_table.rowCount()
            self._tasks_table.insertRow(row)
            self._tasks_table.setItem(row, 0, QTableWidgetItem(task.task_number))
            self._tasks_table.setItem(row, 1, QTableWidgetItem(task.title))
            self._tasks_table.setItem(row, 2, QTableWidgetItem(task.strategy_text))
            self._tasks_table.setItem(row, 3, QTableWidgetItem(task.assignee or ""))
            self._tasks_table.setItem(row, 4, QTableWidgetItem(task.status))
            self._tasks_table.setItem(row, 5, QTableWidgetItem(task.due or ""))
            self._tasks_table.setItem(row, 6, QTableWidgetItem("Yes" if task.is_open else "No"))

    def _populate_history(self, history) -> None:
        self._log_list.clear()
        for entry in history:
            label = f"{entry.ts:%Y-%m-%d %H:%M} – {entry.field}: {entry.old_value or ''} → {entry.new_value or ''}"
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
        QMessageBox.information(
            self,
            "Create Task",
            "Task creation workflow will be available in a future update.",
        )

    def _show_history(self) -> None:
        self._tab_widget.setCurrentIndex(3)

    def _show_snippet(self) -> None:
        if not self._detail:
            QMessageBox.warning(self, "ICS-202", "Save the objective first to generate a snippet.")
            return
        summary = self._detail.summary
        payload = {
            "code": summary.code,
            "text": summary.text,
            "priority": summary.priority,
            "status": summary.status,
            "strategies": [
                {
                    "text": s.text,
                    "status": s.status,
                    "progress_pct": s.progress_pct,
                    "open_tasks": s.open_tasks,
                    "total_tasks": s.total_tasks,
                }
                for s in self._detail.strategies
            ],
        }
        QMessageBox.information(self, "ICS-202", "Snippet prepared. Copy from console output.")
        print(payload)  # noqa: T201

    def _add_strategy(self) -> None:
        if self._objective_id is None:
            QMessageBox.warning(self, "Strategies", "Save the objective before adding strategies.")
            return
        text, ok = QInputDialog.getText(self, "New Strategy", "Strategy description")
        if not ok or not text.strip():
            return
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            return
        try:
            ApiObjectiveRepository(str(incident_id)).add_strategy(self._objective_id, {"text": text.strip()})
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Strategy", f"Failed to add strategy:\n{exc}")
            return
        self._refresh()

    def _edit_strategy(self) -> None:
        current = self._current_strategy_id()
        if current is None:
            return
        row = self._strategies_table.currentRow()
        existing_text = self._strategies_table.item(row, 0).text() if row >= 0 else ""
        text, ok = QInputDialog.getText(self, "Edit Strategy", "Strategy description", text=existing_text)
        if not ok:
            return
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            return
        try:
            ApiObjectiveRepository(str(incident_id)).update_strategy(self._objective_id, current, {"text": text.strip()})
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Strategy", f"Failed to update strategy:\n{exc}")
            return
        self._refresh()

    def _delete_strategy(self) -> None:
        current = self._current_strategy_id()
        if current is None:
            return
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            return
        if QMessageBox.question(
            self,
            "Delete Strategy",
            "Remove the selected strategy?",
        ) != QMessageBox.Yes:
            return
        try:
            ApiObjectiveRepository(str(incident_id)).delete_strategy(self._objective_id, current)
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Strategy", f"Failed to delete strategy:\n{exc}")
            return
        self._refresh()

    def _current_strategy_id(self) -> Optional[str]:
        row = self._strategies_table.currentRow()
        if row < 0:
            return None
        item = self._strategies_table.item(row, 0)
        if not item:
            return None
        data = item.data(Qt.UserRole)
        return str(data) if data is not None else None

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        super().closeEvent(event)
        self._detail = None
