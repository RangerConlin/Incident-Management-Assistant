from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QComboBox,
    QLineEdit,
)
from PySide6.QtCore import Qt

from ..models.repository import PublicInfoRepository


class QueuePanel(QWidget):
    """UI panel showing list of PIO messages."""

    def __init__(self, mission_id: str, current_user: dict, parent=None):
        super().__init__(parent)
        self.repo = PublicInfoRepository(mission_id)
        self.current_user = current_user

        layout = QVBoxLayout(self)

        # Filters
        filter_layout = QHBoxLayout()
        self.status_filter = QComboBox()
        self.status_filter.addItem("All", None)
        for status in ["Draft", "InReview", "Approved", "Published", "Archived"]:
            self.status_filter.addItem(status, status)
        self.status_filter.currentIndexChanged.connect(self.refresh)
        filter_layout.addWidget(self.status_filter)

        self.type_filter = QComboBox()
        self.type_filter.addItem("All", None)
        for t in ["PressRelease", "Advisory", "SituationUpdate"]:
            self.type_filter.addItem(t, t)
        self.type_filter.currentIndexChanged.connect(self.refresh)
        filter_layout.addWidget(self.type_filter)

        self.audience_filter = QComboBox()
        self.audience_filter.addItem("All", None)
        for a in ["Public", "Agency", "Internal"]:
            self.audience_filter.addItem(a, a)
        self.audience_filter.currentIndexChanged.connect(self.refresh)
        filter_layout.addWidget(self.audience_filter)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search...")
        self.search_box.textChanged.connect(self.refresh)
        filter_layout.addWidget(self.search_box)

        layout.addLayout(filter_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Status",
            "Type",
            "Audience",
            "Title",
            "Updated",
            "Author",
        ])
        layout.addWidget(self.table)

        # Initial load
        self.refresh()

    def refresh(self):
        status = self.status_filter.currentData()
        mtype = self.type_filter.currentData()
        audience = self.audience_filter.currentData()
        q = self.search_box.text() or None
        messages = self.repo.list_messages(
            status=status, type=mtype, audience=audience, q=q
        )
        self.table.setRowCount(0)
        for msg in messages:
            row = self.table.rowCount()
            self.table.insertRow(row)
            items = [
                msg["status"],
                msg["type"],
                msg["audience"],
                msg["title"],
                msg["updated_at"],
                str(msg["created_by"]),
            ]
            for col, text in enumerate(items):
                self.table.setItem(row, col, QTableWidgetItem(text))
