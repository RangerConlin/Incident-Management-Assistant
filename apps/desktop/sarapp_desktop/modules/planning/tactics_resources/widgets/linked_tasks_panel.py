"""
LinkedTasksPanel
================
Tab widget for viewing and managing Operations task links on a Work Assignment.

Users can:
  - Create a new Operations task pre-filled from this assignment
  - Link an existing task
  - Open the Task Detail Window for a linked task
  - Unlink a task
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from modules.planning.tactics_resources.data.work_assignment_repository import WorkAssignmentRepository
from utils.table_view_styles import apply_statusboard_table_behavior
from utils.styles import get_palette, task_status_colors

# Optional integration with Operations Taskings
try:
    from modules.operations.taskings.windows import open_task_detail_window  # type: ignore
    _HAS_TASK_WINDOW = True
except ImportError:
    _HAS_TASK_WINDOW = False


_PRIORITY_LABELS = {1: "Low", 2: "Medium", 3: "High", 4: "Critical"}


def _priority_label(value: object) -> str:
    if isinstance(value, int):
        return _PRIORITY_LABELS.get(value, str(value))
    text = str(value or "").strip()
    if text.isdigit():
        return _PRIORITY_LABELS.get(int(text), text)
    return text


class LinkedTasksPanel(QWidget):
    """Displays and manages Operations task links for one Work Assignment."""

    def __init__(
        self,
        work_assignment_id: int,
        db_path: str | None = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._work_assignment_id = work_assignment_id
        self._db_path = db_path

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Toolbar
        btn_bar = QHBoxLayout()
        self._summary_label = QLabel("")
        self._summary_label.setStyleSheet(f"color:{get_palette().get('fg_muted').name()};")
        self._create_btn = QPushButton("Generate Task")
        self._link_btn = QPushButton("Link Existing")
        self._open_btn = QPushButton("Open Task Detail")
        self._unlink_btn = QPushButton("Unlink Task")
        self._refresh_btn = QPushButton("Refresh")
        btn_bar.addWidget(self._summary_label)
        btn_bar.addStretch(1)
        btn_bar.addWidget(self._link_btn)
        btn_bar.addWidget(self._create_btn)
        layout.addLayout(btn_bar)

        if not _HAS_TASK_WINDOW:
            note = QLabel("Note: Task Detail Window launcher not found — Open Task Detail will show task info only.")
            note.setStyleSheet(f"color:{get_palette().get('fg_muted').name()}; font-style: italic;")
            layout.addWidget(note)

        # Task table
        columns = ["Task #", "Name", "Status", "Team", "Priority"]
        self._table = QTableWidget(0, len(columns))
        self._table.setHorizontalHeaderLabels(columns)
        self._table.verticalHeader().setVisible(False)
        apply_statusboard_table_behavior(self._table, stretch_last_section=False)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._table.doubleClicked.connect(self._open_task)
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._table)

        self._create_btn.clicked.connect(self._create_task)
        self._link_btn.clicked.connect(self._link_existing)
        self._open_btn.clicked.connect(self._open_task)
        self._unlink_btn.clicked.connect(self._unlink_task)
        self._refresh_btn.clicked.connect(self.reload)

        self.reload()

    # ------------------------------------------------------------------
    def reload(self) -> None:
        try:
            repo = WorkAssignmentRepository(self._db_path)
            links = repo.list_linked_tasks(self._work_assignment_id)
        except Exception as exc:
            QMessageBox.critical(self, "Tasks", f"Failed to load linked tasks:\n{exc}")
            return
        self._table.setRowCount(0)
        self._summary_label.setText(f"{len(links)} linked tasks")
        for link in links:
            task_info = self._fetch_task_info(link.task_id)
            row = self._table.rowCount()
            self._table.insertRow(row)
            status = task_info.get("status", "")
            brushes = task_status_colors().get(status.lower())
            row_items = [
                QTableWidgetItem(task_info.get("task_number", "")),
                QTableWidgetItem(task_info.get("title", "")),
                QTableWidgetItem(status),
                QTableWidgetItem(task_info.get("team_display", "")),
                QTableWidgetItem(task_info.get("priority", "")),
            ]
            if brushes:
                for row_item in row_items:
                    row_item.setBackground(brushes["bg"])
                    row_item.setForeground(brushes["fg"])
            full_team_text = task_info.get("team", "")
            if full_team_text:
                row_items[3].setToolTip(full_team_text)
            for column, item in enumerate(row_items):
                self._table.setItem(row, column, item)
            # Store link.id and task_id in UserRole
            self._table.item(row, 0).setData(Qt.UserRole, (link.id, link.task_id))

    def _fetch_task_info(self, task_id: int) -> dict:
        """Get task data from the API."""
        try:
            from utils.api_client import api_client
            from utils.incident_context import get_active_incident_id
            iid = get_active_incident_id()
            if not iid:
                return {}
            doc = api_client.get(f"/api/incidents/{iid}/operations/tasks/{task_id}")
            if doc:
                assigned = [
                    str(tt.get("team_name") or f"Team {tt.get('team_id')}")
                    for tt in (doc.get("task_teams") or doc.get("assigned_teams") or [])
                    if tt.get("team_name") or tt.get("team_id") is not None
                ]
                team_text = ", ".join(assigned)
                team_display = team_text if len(assigned) <= 2 else f"{len(assigned)} teams"
                return {
                    "task_number": str(doc.get("task_id") or ""),
                    "title": doc.get("title", ""),
                    "category": doc.get("category", ""),
                    "team": team_text,
                    "team_display": team_display,
                    "status": doc.get("status", ""),
                    "priority": _priority_label(doc.get("priority", "")),
                }
        except Exception:
            pass
        return {"task_number": ""}

    def _current_link_and_task(self) -> tuple[int | None, int | None]:
        row = self._table.currentRow()
        if row < 0:
            return None, None
        item = self._table.item(row, 0)
        if not item:
            return None, None
        data = item.data(Qt.UserRole)
        if isinstance(data, tuple) and len(data) == 2:
            return data
        return None, None

    # ------------------------------------------------------------------

    def _show_context_menu(self, pos) -> None:
        item = self._table.itemAt(pos)
        if item is not None:
            self._table.setCurrentCell(item.row(), item.column())
        if self._table.currentRow() < 0:
            return
        menu = QMenu(self)
        menu.addAction("Open Task Detail", self._open_task)
        menu.addAction("Unlink Task", self._unlink_task)
        menu.addSeparator()
        menu.addAction("Refresh", self.reload)
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _create_task(self) -> None:
        """Create a new Operations task from this work assignment."""
        try:
            repo = WorkAssignmentRepository(self._db_path)
            task_id = repo.create_task_from_work_assignment(self._work_assignment_id)
        except Exception as exc:
            QMessageBox.critical(self, "Create Task", f"Failed to create task:\n{exc}")
            return

        if task_id is None:
            QMessageBox.information(
                self,
                "Create Task",
                "Task creation is not available — the Taskings module was not found.\n"
                "Record the link manually once a task is created.",
            )
            return

        QMessageBox.information(self, "Create Task", f"Operations task created (ID: {task_id}).")
        self.reload()

    def _link_existing(self) -> None:
        """Show a dialog to find and link an existing Operations task."""
        dialog = _LinkTaskDialog(self._work_assignment_id, self._db_path, parent=self)
        dialog.exec()
        self.reload()

    def _open_task(self) -> None:
        _, task_id = self._current_link_and_task()
        if task_id is None:
            QMessageBox.information(self, "Open Task", "Select a linked task first.")
            return
        if _HAS_TASK_WINDOW:
            try:
                open_task_detail_window(task_id)
                return
            except Exception:
                pass
        # Fallback: show task info in a message box
        task_info = self._fetch_task_info(task_id)
        if task_info:
            details = "\n".join(f"{k}: {v}" for k, v in task_info.items() if v)
            QMessageBox.information(self, f"Task {task_id}", details or f"Task ID: {task_id}")
        else:
            QMessageBox.information(self, "Open Task", f"Task ID: {task_id} — detail window not available.")

    def _unlink_task(self) -> None:
        link_id, _ = self._current_link_and_task()
        if link_id is None:
            QMessageBox.information(self, "Unlink", "Select a task to unlink.")
            return
        if QMessageBox.question(
            self, "Unlink Task", "Remove this task link from the work assignment?"
        ) != QMessageBox.Yes:
            return
        try:
            repo = WorkAssignmentRepository(self._db_path)
            repo.unlink_task_for_wa(self._work_assignment_id, link_id)
        except Exception as exc:
            QMessageBox.critical(self, "Unlink", f"Failed to unlink task:\n{exc}")
            return
        self.reload()


# ---------------------------------------------------------------------------
# Link existing task dialog
# ---------------------------------------------------------------------------

class _LinkTaskDialog(QDialog):
    """Simple dialog to search and link an existing Operations task."""

    def __init__(
        self,
        work_assignment_id: int,
        db_path: str | None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Link Existing Task")
        self.setModal(True)
        self.setMinimumWidth(500)
        self._work_assignment_id = work_assignment_id
        self._db_path = db_path

        layout = QVBoxLayout(self)

        search_bar = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search tasks by title or ID…")
        search_btn = QPushButton("Search")
        search_bar.addWidget(self._search_edit)
        search_bar.addWidget(search_btn)
        layout.addLayout(search_bar)

        columns = ["Task ID", "Title", "Status", "Priority"]
        self._task_table = QTableWidget(0, len(columns))
        self._task_table.setHorizontalHeaderLabels(columns)
        self._task_table.verticalHeader().setVisible(False)
        apply_statusboard_table_behavior(self._task_table, stretch_last_section=True)
        layout.addWidget(self._task_table)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._link_selected)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        search_btn.clicked.connect(self._search_tasks)
        self._search_tasks()  # pre-load all tasks on open

    def _search_tasks(self) -> None:
        search_text = self._search_edit.text().strip().lower()
        self._task_table.setRowCount(0)
        try:
            from utils.api_client import api_client
            from utils.incident_context import get_active_incident_id
            iid = get_active_incident_id()
            if not iid:
                return
            rows = api_client.get(f"/api/incidents/{iid}/operations/tasks-for-assignment") or []
        except Exception:
            return
        for r in rows:
            numeric_id = r.get("id") or r.get("int_id")
            tid = r.get("task_id") or ""
            title = r.get("title", "")
            status = r.get("status", "")
            priority = _priority_label(r.get("priority", ""))
            if search_text and search_text not in str(tid).lower() and search_text not in title.lower():
                continue
            row_idx = self._task_table.rowCount()
            self._task_table.insertRow(row_idx)
            self._task_table.setItem(row_idx, 0, QTableWidgetItem(str(tid)))
            self._task_table.setItem(row_idx, 1, QTableWidgetItem(title))
            self._task_table.setItem(row_idx, 2, QTableWidgetItem(status))
            self._task_table.setItem(row_idx, 3, QTableWidgetItem(priority))
            self._task_table.item(row_idx, 0).setData(Qt.UserRole, numeric_id)

    def _link_selected(self) -> None:
        # If task list available, use selection
        task_id: int | None = None
        row = self._task_table.currentRow()
        if row >= 0:
            item = self._task_table.item(row, 0)
            if item:
                try:
                    task_id = int(item.data(Qt.UserRole) or item.text())
                except (ValueError, TypeError):
                    pass

        # If no table selection, try to parse search field as a numeric ID
        if task_id is None:
            text = self._search_edit.text().strip()
            try:
                task_id = int(text)
            except (ValueError, TypeError):
                QMessageBox.warning(self, "Link Task", "Select a task or enter a numeric Task ID.")
                return

        try:
            repo = WorkAssignmentRepository(self._db_path)
            result = repo.link_existing_task(
                self._work_assignment_id, task_id, link_type="Linked Existing"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Link Task", f"Failed to link task:\n{exc}")
            return

        if result is None:
            QMessageBox.information(
                self, "Link Task", f"Task {task_id} is already linked to this work assignment."
            )
        else:
            QMessageBox.information(self, "Link Task", f"Task {task_id} linked successfully.")
        self.accept()
