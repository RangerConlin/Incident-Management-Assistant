"""IntelLogTab — table view of the Intel activity timeline."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QDateEdit,
)
from PySide6.QtCore import Qt, QDate, Signal

from modules.intel.models.log_entry import IntelLogEntry
from modules.intel.services.intel_service import IntelService
from utils.table_view_styles import apply_statusboard_table_behavior
from utils.styles import intel_entity_colors, subscribe_theme


def _color_blob(hex_color: str, label: str) -> str:
    return (
        f'<span style="color: {hex_color}; font-size: 16px; vertical-align: middle;">&#9679;</span> '
        f'<span style="vertical-align: middle;">{label}</span>'
    )


# Maps display label → (entity_type value, ...)
_ENTITY_FILTER_ITEMS = [
    ("All Entities",  None),
    ("Subject",       "subject"),
    ("Lead",          "lead"),
    ("Intel Item",    "item"),
    ("Assessment",    "assessment"),
    ("Observation",   "observation"),
    ("Attachment",    "attachment"),
    ("Report",        "report"),
    ("Form",          "form"),
]

# Maps display label → event_type value
_EVENT_FILTER_ITEMS = [
    ("All Events",          None),
    ("Created",             "created"),
    ("Updated",             "updated"),
    ("Assigned",            "assigned"),
    ("Status Changed",      "status_changed"),
    ("Priority Changed",    "priority_changed"),
    ("Converted",           "converted"),
    ("Closed",              "closed"),
    ("Completed",           "completed"),
    ("Rejected",            "rejected"),
    ("Archived",            "archived"),
    ("Reopened",            "reopened"),
    ("Linked",              "linked"),
    ("Unlinked",            "unlinked"),
    ("Observation Added",   "observation_added"),
    ("Observation Updated", "observation_updated"),
    ("Attachment Added",    "attachment_added"),
    ("Attachment Removed",  "attachment_removed"),
    ("Form Linked",         "form_linked"),
    ("Form Unlinked",       "form_unlinked"),
]

# entity types that support navigation on double-click
_NAVIGABLE_ENTITIES = {"lead", "item", "subject", "assessment", "observation"}


class IntelLogTab(QWidget):
    """Chronological activity log for all Intel module records."""

    navigate_to_record = Signal(str, str)  # (entity_type, entity_id)

    _COLS = ["Time", "Date", "Entity", "Event", "Summary", "Actor"]

    def __init__(self, service: IntelService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._all_entries: list[IntelLogEntry] = []
        self._filtered: list[IntelLogEntry] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        # ── Toolbar row 1: title + entity + event + search + refresh ──
        toolbar = QHBoxLayout()
        title = QLabel("Intel Log")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: palette(windowText);")

        self._entity_filter = QComboBox()
        self._entity_filter.addItems([label for label, _ in _ENTITY_FILTER_ITEMS])
        self._entity_filter.currentTextChanged.connect(self._apply_filter)

        self._event_filter = QComboBox()
        self._event_filter.addItems([label for label, _ in _EVENT_FILTER_ITEMS])
        self._event_filter.currentTextChanged.connect(self._apply_filter)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search…")
        self._search.setFixedWidth(200)
        self._search.textChanged.connect(self._apply_filter)

        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedWidth(32)
        refresh_btn.clicked.connect(self.refresh)

        toolbar.addWidget(title)
        toolbar.addStretch()
        toolbar.addWidget(self._entity_filter)
        toolbar.addWidget(self._event_filter)
        toolbar.addWidget(self._search)
        toolbar.addWidget(refresh_btn)
        layout.addLayout(toolbar)

        # ── Toolbar row 2: date range ──────────────────────────────────
        date_row = QHBoxLayout()
        date_row.setSpacing(6)

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

        date_row.addStretch()
        date_row.addWidget(QLabel("From:"))
        date_row.addWidget(self._date_from)
        date_row.addWidget(QLabel("To:"))
        date_row.addWidget(self._date_to)
        layout.addLayout(date_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        self._table = QTableWidget()
        self._table.setColumnCount(len(self._COLS))
        self._table.setHorizontalHeaderLabels(self._COLS)
        apply_statusboard_table_behavior(self._table)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setSortingEnabled(False)  # log is chronological, preserve order
        self._table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)
        self._legend = QLabel()
        self._legend.setTextFormat(Qt.RichText)
        self._legend.setStyleSheet("font-size: 11px; color: palette(placeholderText);")
        layout.addWidget(self._legend)
        self._update_legend()

        subscribe_theme(self, self._on_theme_changed)
        self.refresh()

    def _update_legend(self) -> None:
        colors = intel_entity_colors()
        self._legend.setText(
            "  ".join([
                _color_blob(colors["lead"]["fg"].color().name(), "Lead"),
                _color_blob(colors["subject"]["fg"].color().name(), "Subject"),
                _color_blob(colors["item"]["fg"].color().name(), "Item"),
                _color_blob(colors["assessment"]["fg"].color().name(), "Assessment"),
            ])
        )

    def _on_theme_changed(self, *_: object) -> None:
        self._update_legend()
        self._render()

    def refresh(self) -> None:
        if self._service is None:
            return
        since = self._date_from.date().toString("yyyy-MM-dd") + "T00:00:00"
        until = self._date_to.date().toString("yyyy-MM-dd") + "T23:59:59"
        self._all_entries = self._service.log.list(since=since, until=until, limit=500)
        self._apply_filter()

    def _apply_filter(self) -> None:
        q = self._search.text().lower()

        entity_map = {label: val for label, val in _ENTITY_FILTER_ITEMS}
        entity_key = entity_map.get(self._entity_filter.currentText())

        event_map = {label: val for label, val in _EVENT_FILTER_ITEMS}
        event_key = event_map.get(self._event_filter.currentText())

        def _matches(e: IntelLogEntry) -> bool:
            if entity_key and e.entity_type != entity_key:
                return False
            if event_key and e.event_type != event_key:
                return False
            if q:
                search_text = " ".join(filter(None, [
                    e.summary,
                    e.actor,
                    e.entity_label,
                    e.event_label,
                ])).lower()
                return q in search_text
            return True

        self._filtered = [e for e in self._all_entries if _matches(e)]
        self._render()

    def _render(self) -> None:
        self._table.setRowCount(len(self._filtered))
        for row, e in enumerate(self._filtered):
            ts = e.timestamp or ""
            time_str = ts[11:16] if len(ts) >= 16 else ""
            date_str = ts[:10] if ts else ""
            cells = [
                time_str,
                date_str,
                e.entity_label,
                e.event_label,
                e.summary or "",
                e.actor or "",
            ]
            entity_colors = intel_entity_colors().get(e.entity_type or "")
            row_brush = entity_colors["bg"] if entity_colors else None
            fg_brush = entity_colors["fg"] if entity_colors else None
            for col, val in enumerate(cells):
                item = QTableWidgetItem(val)
                if row_brush:
                    item.setBackground(row_brush)
                if fg_brush and col == 2:
                    item.setForeground(fg_brush)
                self._table.setItem(row, col, item)
            # Indicate navigable rows with a tooltip
            if e.entity_type in _NAVIGABLE_ENTITIES and e.entity_id:
                for col in range(len(self._COLS)):
                    cell = self._table.item(row, col)
                    if cell:
                        cell.setToolTip("Double-click to open related record")
            self._table.setRowHeight(row, 30)

        for col in (0, 1, 2, 3, 5):
            self._table.resizeColumnToContents(col)

    def _on_double_click(self, index) -> None:
        row = index.row()
        if 0 <= row < len(self._filtered):
            e = self._filtered[row]
            if e.entity_type in _NAVIGABLE_ENTITIES and e.entity_id:
                self.navigate_to_record.emit(e.entity_type, e.entity_id)
