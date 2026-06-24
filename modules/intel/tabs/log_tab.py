"""IntelLogTab — table view of the Intel activity timeline."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QDateEdit,
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QBrush

from modules.intel.models.log_entry import IntelLogEntry
from modules.intel.services.intel_service import IntelService


_ENTITY_FG: dict[str, str] = {
    "subject":    "#cf4444",
    "lead":       "#d29922",
    "item":       "#4a9eff",
    "assessment": "#2da44e",
    "report":     "#8b949e",
}

_ENTITY_ROW_BG: dict[str, QColor] = {
    "subject":    QColor(180, 40,  40,  90),
    "lead":       QColor(180, 140, 20,  80),
    "item":       QColor(30,  100, 200, 80),
    "assessment": QColor(40,  160, 80,  70),
    "report":     QColor(100, 100, 100, 60),
}


class IntelLogTab(QWidget):
    _COLS = ["Time", "Date", "Entity", "Event", "Summary", "Actor"]

    def __init__(self, service: IntelService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._all_entries: list[IntelLogEntry] = []
        self._filtered: list[IntelLogEntry] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()
        title = QLabel("Intel Log")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: palette(windowText);")

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search…")
        self._search.setFixedWidth(200)
        self._search.textChanged.connect(self._apply_filter)

        self._entity_filter = QComboBox()
        self._entity_filter.addItems([
            "All Entities", "Subject", "Lead", "Intel Item", "Assessment", "Report",
        ])
        self._entity_filter.currentTextChanged.connect(self._apply_filter)

        self._date_from = QDateEdit()
        self._date_from.setCalendarPopup(True)
        self._date_from.setDate(QDate.currentDate().addDays(-7))
        self._date_from.setDisplayFormat("MM/dd/yyyy")
        self._date_from.dateChanged.connect(self.refresh)

        self._date_to = QDateEdit()
        self._date_to.setCalendarPopup(True)
        self._date_to.setDate(QDate.currentDate())
        self._date_to.setDisplayFormat("MM/dd/yyyy")
        self._date_to.dateChanged.connect(self.refresh)

        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedWidth(32)
        refresh_btn.clicked.connect(self.refresh)

        toolbar.addWidget(title)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("From:"))
        toolbar.addWidget(self._date_from)
        toolbar.addWidget(QLabel("To:"))
        toolbar.addWidget(self._date_to)
        toolbar.addWidget(self._entity_filter)
        toolbar.addWidget(self._search)
        toolbar.addWidget(refresh_btn)
        layout.addLayout(toolbar)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        self._table = QTableWidget()
        self._table.setColumnCount(len(self._COLS))
        self._table.setHorizontalHeaderLabels(self._COLS)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setSortingEnabled(False)  # log is chronological, preserve order
        layout.addWidget(self._table)

        self.refresh()

    def refresh(self) -> None:
        if self._service is None:
            return
        since = self._date_from.date().toString("yyyy-MM-dd") + "T00:00:00"
        until = self._date_to.date().toString("yyyy-MM-dd") + "T23:59:59"
        self._all_entries = self._service.log.list(since=since, until=until, limit=500)
        self._apply_filter()

    def _apply_filter(self) -> None:
        q = self._search.text().lower()
        entity_map = {
            "Subject": "subject", "Lead": "lead",
            "Intel Item": "item", "Assessment": "assessment", "Report": "report",
        }
        entity_key = entity_map.get(self._entity_filter.currentText())
        self._filtered = [
            e for e in self._all_entries
            if (not q or q in e.summary.lower() or q in (e.actor or "").lower())
            and (not entity_key or e.entity_type == entity_key)
        ]
        self._render()

    def _render(self) -> None:
        self._table.setRowCount(len(self._filtered))
        for row, e in enumerate(self._filtered):
            ts = e.timestamp or ""
            time_str = ts[11:16] if len(ts) >= 16 else ""
            date_str = ts[:10] if ts else ""
            entity_label = e.entity_type.title() if e.entity_type else ""
            event_label = (e.event_type or "").replace("_", " ").title()
            cells = [time_str, date_str, entity_label, event_label, e.summary or "", e.actor or ""]
            bg = _ENTITY_ROW_BG.get(e.entity_type or "")
            row_brush = QBrush(bg) if bg else None
            fg = _ENTITY_FG.get(e.entity_type or "")
            for col, val in enumerate(cells):
                item = QTableWidgetItem(val)
                if row_brush:
                    item.setBackground(row_brush)
                if fg and col == 2:
                    item.setForeground(QColor(fg))
                self._table.setItem(row, col, item)
            self._table.setRowHeight(row, 30)

        for col in (0, 1, 2, 3, 5):
            self._table.resizeColumnToContents(col)
