from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QMenu, QAbstractItemView, QHBoxLayout, QPushButton, QHeaderView
from PySide6.QtCore import Qt
from utils.styles import task_status_colors, subscribe_theme
from utils.audit import write_audit

# Require incident DB repository (no sample fallback)
try:
    from modules.operations.data.repository import fetch_task_rows, set_task_status  # type: ignore
except Exception:
    fetch_task_rows = None  # type: ignore[assignment]

class TaskStatusPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        # Header actions
        header_bar = QWidget()
        hb = QHBoxLayout(header_bar)
        try:
            hb.setContentsMargins(0, 0, 0, 0)
            hb.setSpacing(6)
        except Exception:
            pass
        btn_open = QPushButton("Open Detail")
        btn_new = QPushButton("New Task")
        btn_open.clicked.connect(self._on_open_detail)
        btn_new.clicked.connect(self._on_new_task)
        hb.addWidget(btn_open)
        hb.addWidget(btn_new)

        self.table = QTableWidget()
        # Make table read-only; edits go through context menus / detail windows
        try:
            self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        except Exception:
            pass
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        try:
            self.table.itemDoubleClicked.connect(lambda item: self.view_task_detail(item.row()))
        except Exception:
            pass
        layout.addWidget(header_bar)
        layout.addWidget(self.table)

        # Set column headers
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Task #", "Task Name", "Assigned Team(s)", "Status", "Priority", "Location"
        ])
        try:
            hdr = self.table.horizontalHeader()
            hdr.setSectionsMovable(True)
            hdr.setStretchLastSection(False)
        except Exception:
            pass
        # Initial load
        self.reload()
        # React to incident changes
        try:
            from utils.app_signals import app_signals
            app_signals.incidentChanged.connect(lambda *_: self.reload())
        except Exception:
            pass
        try:
            subscribe_theme(self, lambda *_: self._recolor_all())
        except Exception:
            pass

    def add_task(self, task):
        row = self.table.rowCount()
        self.table.insertRow(row)

        items = [
                QTableWidgetItem(task.number),
                QTableWidgetItem(task.name),
                QTableWidgetItem(", ".join(task.assigned_teams)),
                QTableWidgetItem(task.status),
                QTableWidgetItem(task.priority),
                QTableWidgetItem(task.location)
        ]

        for col, item in enumerate(items):
            self.table.setItem(row, col, item)

        self.set_row_color_by_status(row, task.status)

    def _add_task_row(self, data: dict) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        teams = data.get("assigned_teams") or []
        teams_str = ", ".join(map(str, teams)) if isinstance(teams, (list, tuple)) else str(teams)
        status_key = str(data.get("status", ""))
        status_display = status_key.title() if status_key else ""
        vals = [
            str(data.get("number", "")),
            str(data.get("name", "")),
            teams_str,
            status_display,
            str(data.get("priority", "")),
            str(data.get("location", "")),
        ]
        for col, text in enumerate(vals):
            item = QTableWidgetItem(text)
            if col == 0:
                try:
                    item.setData(Qt.UserRole, int(data.get("id")))
                except Exception:
                    pass
            self.table.setItem(row, col, item)
        # Use the original key for color mapping (row-wide coloring)
        self.set_row_color_by_status(row, status_key)

    def reload(self) -> None:
        # Clear and load fresh data from incident DB
        try:
            self.table.setRowCount(0)
            if not fetch_task_rows:
                raise RuntimeError("DB repository not available")
            rows = fetch_task_rows()
            for data in rows:
                self._add_task_row(data)
        except Exception as e:
            from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QMenu, QAbstractItemView, QHBoxLayout, QPushButton, QHeaderView
            QMessageBox.critical(self, "Task Board Error", f"Failed to load tasks from incident DB:\n{e}")

    def set_row_color_by_status(self, row, status):
        style = task_status_colors().get(status.lower())
        if not style:
            return

        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item:
                item.setBackground(style["bg"])
                item.setForeground(style["fg"])

    def _recolor_all(self) -> None:
        try:
            status_col = 3
            rows = self.table.rowCount()
            for r in range(rows):
                item = self.table.item(r, status_col)
                status = (item.text() if item else "").strip().lower()
                self.set_row_color_by_status(r, status)
        except Exception:
            pass

    def show_context_menu(self, position):
        row = self.table.indexAt(position).row()
        if row < 0:
            return

        menu = QMenu(self)

        # Top-level actions
        menu.addAction("View Task Detail (Widget)", lambda: self.view_task_detail(row))
        menu.addAction("View Task Detail (QML)", lambda: self.view_task_detail_qml(row))

        # Add separator
        menu.addSeparator()

        # Flat list of status options
        for status in task_status_colors():
            menu.addAction(status.title(), lambda s=status: self.change_status(row, s))

        # Show the menu
        menu.exec(self.table.viewport().mapToGlobal(position))

    def view_team_detail(self, row):
        print(f"Viewing team detail for row {row}")

    def view_task_detail(self, row):
        try:
            # Prefer stored DB task id on first column
            item = self.table.item(row, 0)
            task_id = int(item.data(Qt.UserRole)) if item and item.data(Qt.UserRole) is not None else None
            if task_id is None:
                raise RuntimeError("No task id associated with row")
            from modules.operations.taskings.windows import open_task_detail_window
            open_task_detail_window(task_id)
        except Exception as e:
            print(f"Failed to open Task Detail Window: {e}")

    def view_task_detail_qml(self, row):
        try:
            item = self.table.item(row, 0)
            task_id = int(item.data(Qt.UserRole)) if item and item.data(Qt.UserRole) is not None else None
            if task_id is None:
                raise RuntimeError("No task id associated with row")
            from modules.operations.taskings.windows import open_task_detail_window_qml
            open_task_detail_window_qml(task_id)
        except Exception as e:
            print(f"Failed to open QML Task Detail Window: {e}")

    def change_status(self, row, new_status):
        try:
            item_id = self.table.item(row, 0)
            task_id = int(item_id.data(Qt.UserRole)) if item_id and item_id.data(Qt.UserRole) is not None else None
            if not task_id:
                raise RuntimeError("No task id associated with row")
            if not set_task_status:
                raise RuntimeError("DB repository not available")
            item_status = self.table.item(row, 3)
            old_status = (item_status.text() if item_status else "").strip().lower()
            set_task_status(task_id, str(new_status))
            # Update UI
            display = str(new_status).title()
            self.table.item(row, 3).setText(display)
            self.set_row_color_by_status(row, str(new_status))
            write_audit("status.change", {"panel": "task", "id": task_id, "old": old_status, "new": str(new_status)})
        except Exception as e:
            from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QMenu, QAbstractItemView, QHBoxLayout, QPushButton, QHeaderView
            QMessageBox.critical(self, "Update Failed", f"Unable to update task status in DB:\n{e}")

    def _on_open_detail(self) -> None:
        row = self.table.currentRow()
        if row < 0 and self.table.selectedIndexes():
            row = self.table.selectedIndexes()[0].row()
        if row < 0:
            from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QMenu, QAbstractItemView, QHBoxLayout, QPushButton, QHeaderView
            QMessageBox.information(self, "Open Detail", "Select a task row first.")
            return
        self.view_task_detail(row)

    def _on_new_task(self) -> None:
        try:
            from modules.operations.taskings.repository import create_task
            new_id = create_task(title="<New Task>")
            # Reload table and open detail for the new task
            self.reload()
            from modules.operations.taskings.windows import open_task_detail_window
            open_task_detail_window(new_id)
        except Exception as e:
            from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QMenu, QAbstractItemView, QHBoxLayout, QPushButton, QHeaderView
            QMessageBox.critical(self, "New Task", f"Failed to create new task:\n{e}")


