from __future__ import annotations

"""Modeless editor dialog for incident objectives."""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules._infra.repository import with_incident_session
from modules.command.models.objectives import (
    PRIORITY_VALUES,
    STATUS_VALUES,
    ObjectiveDetail,
    ObjectiveRepository,
    ObjectiveStrategyView,
)
from utils import incident_context


class ObjectiveDetailDialog(QDialog):
    """Qt Widgets dialog that keeps focus on strategic outcomes."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setModal(False)
        self.setWindowTitle("Objective Detail")
        self._objective_id: Optional[int] = None
        self._detail: Optional[ObjectiveDetail] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._header_box = self._build_header()
        layout.addWidget(self._header_box)

        self._tab_widget = QTabWidget(self)
        layout.addWidget(self._tab_widget, 1)

        self._build_strategies_tab()
        self._build_tasks_tab()
        self._build_narrative_tab()
        self._build_log_tab()

        self.resize(960, 640)

    # ------------------------------------------------------------------
    def load_objective(self, objective_id: int) -> None:
        self._objective_id = objective_id
        self._refresh()

    # ------------------------------------------------------------------
    def _build_header(self) -> QWidget:
        container = QGroupBox("Objective")
        form = QFormLayout(container)
        form.setLabelAlignment(Qt.AlignRight)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(6)

        self._code_label = QLabel("OBJ-")
        self._objective_text = QTextEdit()
        self._objective_text.setPlaceholderText("Objective statement")
        self._objective_text.setAcceptRichText(False)
        self._objective_text.setFixedHeight(80)

        self._priority_combo = QComboBox()
        self._priority_combo.addItems([p.title() for p in PRIORITY_VALUES])

        self._status_combo = QComboBox()
        self._status_combo.addItems([s.title() for s in STATUS_VALUES])

        self._owner_edit = QLineEdit()
        self._owner_edit.setPlaceholderText("Owner or Section")

        self._tags_edit = QLineEdit()
        self._tags_edit.setPlaceholderText("Tags (comma separated)")

        self._op_label = QLabel("–")
        self._updated_label = QLabel("–")

        button_row = QHBoxLayout()
        self._save_button = QPushButton("Save")
        self._save_button.clicked.connect(self._save)
        self._create_task_button = QPushButton("Create Task")
        self._create_task_button.clicked.connect(self._create_task)
        self._history_button = QPushButton("History")
        self._history_button.clicked.connect(self._show_history)
        self._snippet_button = QPushButton("ICS-202 Snippet")
        self._snippet_button.clicked.connect(self._show_snippet)
        button_row.addWidget(self._save_button)
        button_row.addWidget(self._create_task_button)
        button_row.addWidget(self._history_button)
        button_row.addWidget(self._snippet_button)
        button_row.addStretch(1)

        form.addRow("Code", self._code_label)
        form.addRow("Objective", self._objective_text)
        form.addRow("Priority", self._priority_combo)
        form.addRow("Status", self._status_combo)
        form.addRow("Owner/Section", self._owner_edit)
        form.addRow("Tags", self._tags_edit)
        form.addRow("OP", self._op_label)
        form.addRow("Updated", self._updated_label)
        form.addRow(button_row)
        return container

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
    def _refresh(self) -> None:
        incident_id = incident_context.get_active_incident()
        if not incident_id or self._objective_id is None:
            return
        try:
            with with_incident_session(str(incident_id)) as session:
                repository = ObjectiveRepository(session, str(incident_id))
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
        self._op_label.setText(str(summary.op_period_id or ""))
        updated_by = summary.updated_by or "Unknown"
        updated_ts = summary.updated_at.isoformat(sep=" ") if summary.updated_at else ""
        self._updated_label.setText(f"{updated_ts} by {updated_by}")
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
        incident_id = incident_context.get_active_incident()
        if not incident_id:
            QMessageBox.warning(self, "Save", "Select an incident before saving objectives.")
            return
        payload = {
            "text": self._objective_text.toPlainText().strip(),
            "priority": self._priority_combo.currentText().lower(),
            "status": self._status_combo.currentText().lower(),
            "owner_section": self._owner_edit.text().strip() or None,
            "tags": [tag.strip() for tag in self._tags_edit.text().split(",") if tag.strip()],
        }
        try:
            with with_incident_session(str(incident_id)) as session:
                repository = ObjectiveRepository(session, str(incident_id))
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

    def _create_task(self) -> None:
        QMessageBox.information(
            self,
            "Create Task",
            "Task creation workflow will be available in a future update.",
        )

    def _show_history(self) -> None:
        self._tab_widget.setCurrentIndex(3)

    def _show_snippet(self) -> None:
        incident_id = incident_context.get_active_incident()
        if not incident_id or self._objective_id is None:
            return
        try:
            with with_incident_session(str(incident_id)) as session:
                repository = ObjectiveRepository(session, str(incident_id))
                payload = repository.export_ics202()
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "ICS-202", f"Failed to prepare snippet:\n{exc}")
            return
        QMessageBox.information(self, "ICS-202", "Snippet prepared. Copy from console output.")
        print(payload)  # noqa: T201

    def _add_strategy(self) -> None:
        if self._objective_id is None:
            QMessageBox.warning(self, "Strategies", "Save the objective before adding strategies.")
            return
        text, ok = QInputDialog.getText(self, "New Strategy", "Strategy description")
        if not ok or not text.strip():
            return
        incident_id = incident_context.get_active_incident()
        if not incident_id:
            return
        try:
            with with_incident_session(str(incident_id)) as session:
                repository = ObjectiveRepository(session, str(incident_id))
                repository.add_strategy(self._objective_id, {"text": text.strip()})
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Strategy", f"Failed to add strategy:\n{exc}")
            return
        self._refresh()

    def _edit_strategy(self) -> None:
        current = self._current_strategy_id()
        if current is None:
            return
        text, ok = QInputDialog.getText(self, "Edit Strategy", "Strategy description")
        if not ok:
            return
        incident_id = incident_context.get_active_incident()
        if not incident_id:
            return
        try:
            with with_incident_session(str(incident_id)) as session:
                repository = ObjectiveRepository(session, str(incident_id))
                repository.update_strategy(self._objective_id, current, {"text": text.strip()})
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Strategy", f"Failed to update strategy:\n{exc}")
            return
        self._refresh()

    def _delete_strategy(self) -> None:
        current = self._current_strategy_id()
        if current is None:
            return
        incident_id = incident_context.get_active_incident()
        if not incident_id:
            return
        if QMessageBox.question(
            self,
            "Delete Strategy",
            "Remove the selected strategy?",
        ) != QMessageBox.Yes:
            return
        try:
            with with_incident_session(str(incident_id)) as session:
                repository = ObjectiveRepository(session, str(incident_id))
                repository.delete_strategy(self._objective_id, current)
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Strategy", f"Failed to delete strategy:\n{exc}")
            return
        self._refresh()

    def _current_strategy_id(self) -> Optional[int]:
        row = self._strategies_table.currentRow()
        if row < 0:
            return None
        item = self._strategies_table.item(row, 0)
        if not item:
            return None
        return int(item.data(Qt.UserRole))

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        super().closeEvent(event)
        self._detail = None
