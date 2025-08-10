from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QMenu
from styles import TEAM_STATUS_COLORS
from PySide6.QtCore import Qt
from data.sample_data import sample_teams



class TeamStatusPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.table)

        # Set column headers
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Sortie #", "Team Name", "Team Leader", "Contact #",
            "Status", "Assignment", "Location"
        ])

        for team in sample_teams:
            self.add_team(team)

    def add_team(self, team):
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Set all column values
        items = [
            QTableWidgetItem(team.sortie),
            QTableWidgetItem(team.name),
            QTableWidgetItem(team.leader),
            QTableWidgetItem(team.contact),
            QTableWidgetItem(team.status),
            QTableWidgetItem(team.assignment),
            QTableWidgetItem(team.location)
        ]

        for col, item in enumerate(items):
            self.table.setItem(row, col, item)

        self.set_row_color_by_status(row, team.status)  # <- calls class-level method below

    def set_row_color_by_status(self, row, status):  # ✅ Now correctly placed
        style = TEAM_STATUS_COLORS.get(status.lower())
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
        menu.addAction("View Team Detail", lambda: self.view_team_detail(row))
        menu.addAction("View Task Detail", lambda: self.view_task_detail(row))

        # Add separator
        menu.addSeparator()

        # Flat list of status options
        for status in TEAM_STATUS_COLORS:
            menu.addAction(status.title(), lambda s=status: self.change_status(row, s))

        # Show the menu
        menu.exec(self.table.viewport().mapToGlobal(position))

    def view_team_detail(self, row):
        print(f"Viewing team detail for row {row}")

    def view_task_detail(self, row):
        print(f"Viewing task detail for row {row}")

    def change_status(self, row, new_status):
        print(f"Changing status for row {row} to {new_status}")
        self.table.item(row, 4).setText(new_status.title())
        self.set_row_color_by_status(row, new_status)


