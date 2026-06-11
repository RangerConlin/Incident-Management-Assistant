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
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules.planning.tactics_resources.data.work_assignment_repository import WorkAssignmentRepository

# Optional integration with Operations Taskings
try:
    from modules.operations.taskings.windows import open_task_detail_window  # type: ignore
    _HAS_TASK_WINDOW = True
except ImportError:
    _HAS_TASK_WINDOW = False


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

        # Toolbar
        btn_bar = QHBoxLayout()
        self._create_btn = QPushButton("Create Operations Task")
        self._link_btn = QPushButton("Link Existing Task")
        self._open_btn = QPushButton("Open Task Detail")
        self._unlink_btn = QPushButton("Unlink Task")
        self._refresh_btn = QPushButton("Refresh")
        for btn in (self._create_btn, self._link_btn, self._open_btn,
                    self._unlink_btn, self._refresh_btn):
            btn_bar.addWidget(btn)
        btn_bar.addStretch(1)
        layout.addLayout(btn_bar)

        if not _HAS_TASK_WINDOW:
            note = QLabel("Note: Task Detail Window launcher not found — Open Task Detail will show task info only.")
            note.setStyleSheet("color: gray; font-style: italic;")
            layout.addWidget(note)

        # Task table
        columns = ["Task ID", "Task Name", "Type", "Assigned Team", "Status", "Priority", "Link Type", "Notes"]
        self._table = QTableWidget(0, len(columns))
        self._table.setHorizontalHeaderLabels(columns)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
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
        for link in links:
            task_info = self._fetch_task_info(link.task_id)
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(str(link.task_id)))
            self._table.setItem(row, 1, QTableWidgetItem(task_info.get("title", "")))
            self._table.setItem(row, 2, QTableWidgetItem(task_info.get("category", "")))
            self._table.setItem(row, 3, QTableWidgetItem(task_info.get("team", "")))
            self._table.setItem(row, 4, QTableWidgetItem(task_info.get("status", "")))
            self._table.setItem(row, 5, QTableWidgetItem(task_info.get("priority", "")))
            self._table.setItem(row, 6, QTableWidgetItem(link.link_type))
            self._table.setItem(row, 7, QTableWidgetItem(link.notes))
            # Store link.id and task_id in UserRole
            self._table.item(row, 0).setData(Qt.UserRole, (link.id, link.task_id))

    def _fetch_task_info(self, task_id: int) -> dict:
        """Get task data directly from the incident DB."""
        try:
            import sqlite3 as _sq
            from utils.incident_context import get_active_incident_db_path
            db_path = self._db_path or str(get_active_incident_db_path())
            conn = _sq.connect(db_path)
            conn.row_factory = _sq.Row
            row = conn.execute(
                "SELECT task_id, title, category, status, priority FROM tasks WHERE id=?",
                (int(task_id),)
            ).fetchone()
            conn.close()
            if row:
                pri_map = {1: "Low", 2: "Medium", 3: "High", 4: "Critical"}
                pri = row["priority"]
                return {
                    "title": row["title"] or "",
                    "category": row["category"] or "",
                    "team": "",
                    "status": row["status"] or "",
                    "priority": pri_map.get(int(pri), str(pri)) if pri is not None else "",
                }
        except Exception:
            pass
        return {}

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
            repo.unlink_task(link_id)
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
        self._task_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._task_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._task_table.horizontalHeader().setStretchLastSection(True)
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
            import sqlite3 as _sq
            from utils.incident_context import get_active_incident_db_path
            db_path = self._db_path or str(get_active_incident_db_path())
            conn = _sq.connect(db_path)
            conn.row_factory = _sq.Row
            rows = conn.execute(
                "SELECT id, task_id, title, status, priority FROM tasks ORDER BY id DESC LIMIT 500"
            ).fetchall()
            conn.close()
        except Exception:
            return
        priority_map = {1: "Low", 2: "Medium", 3: "High", 4: "Critical"}
        for r in rows:
            tid = r["task_id"] or f"T-{r['id']}"
            title = r["title"] or ""
            status = r["status"] or ""
            pri_raw = r["priority"]
            priority = priority_map.get(int(pri_raw), str(pri_raw)) if pri_raw is not None else ""
            if search_text and search_text not in str(tid).lower() and search_text not in title.lower():
                continue
            row_idx = self._task_table.rowCount()
            self._task_table.insertRow(row_idx)
            self._task_table.setItem(row_idx, 0, QTableWidgetItem(str(tid)))
            self._task_table.setItem(row_idx, 1, QTableWidgetItem(title))
            self._task_table.setItem(row_idx, 2, QTableWidgetItem(status))
            self._task_table.setItem(row_idx, 3, QTableWidgetItem(priority))
            self._task_table.item(row_idx, 0).setData(Qt.UserRole, r["id"])

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
