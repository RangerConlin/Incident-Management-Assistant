from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem

from ..models.repository import PublicInfoRepository


class HistoryPanel(QWidget):
    """Read-only panel listing published messages."""

    def __init__(self, mission_id: str, parent=None):
        super().__init__(parent)
        self.repo = PublicInfoRepository(mission_id)

        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Time",
            "Title",
            "Audience",
            "Type",
            "Published By",
        ])
        layout.addWidget(self.table)
        self.refresh()

    def refresh(self):
        self.table.setRowCount(0)
        for msg in self.repo.list_history():
            row = self.table.rowCount()
            self.table.insertRow(row)
            items = [
                msg["published_at"],
                msg["title"],
                msg["audience"],
                msg["type"],
                str(msg.get("approved_by") or ""),
            ]
            for col, text in enumerate(items):
                self.table.setItem(row, col, QTableWidgetItem(text))
