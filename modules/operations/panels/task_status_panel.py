from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QMenu
from styles import TASK_STATUS_COLORS
from PySide6.QtCore import Qt
from data.sample_data import sample_tasks

class TaskStatusPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.table)

        # Set column headers
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Task #", "Task Name", "Assigned Team(s)", "Status", "Priority", "Location"
        ])

        for task in sample_tasks:
            self.add_task(task)

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

    def set_row_color_by_status(self, row, status):
        style = TASK_STATUS_COLORS.get(status.lower())
        if not style:
            return

        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item:
                item.setBackground(style["bg"])
                item.setForeground(style["fg"])

    def show_context_menu(self, position):
        row = self.table.indexAt(position).row()
        if row < 0:
            return

        menu = QMenu(self)

        # Top-level actions
        menu.addAction("View Task Detail", lambda: self.view_task_detail(row))

        # Add separator
        menu.addSeparator()

        # Flat list of status options
        for status in TASK_STATUS_COLORS:
            menu.addAction(status.title(), lambda s=status: self.change_status(row, s))

        # Show the menu
        menu.exec(self.table.viewport().mapToGlobal(position))

    def view_team_detail(self, row):
        print(f"Viewing team detail for row {row}")

    def view_task_detail(self, row):
        print(f"Viewing task detail for row {row}")

    def change_status(self, row, new_status):
        print(f"Changing status for row {row} to {new_status}")
        self.table.item(row, 3).setText(new_status.title())
        self.set_row_color_by_status(row, new_status)
