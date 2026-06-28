"""SubjectsTab — table view for Intel subjects."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush

from modules.intel.models.subjects import Subject, SUBJECT_TYPES, SubjectType
from modules.intel.services.intel_service import IntelService
from utils.table_view_styles import apply_statusboard_table_behavior

# Row tint colors (ARGB — semi-transparent so text stays readable)
_ROW_COLORS: dict[str, QColor] = {
    "missing":  QColor(180, 40,  40,  120),
    "located":  QColor(40,  160, 80,  100),
    "deceased": QColor(100, 100, 100, 90),
}


def _row_color(subject: Subject) -> QColor | None:
    if subject.subject_type == SubjectType.MISSING_PERSON:
        return _ROW_COLORS["missing"]
    if (subject.status or "").lower() == "located":
        return _ROW_COLORS["located"]
    if (subject.status or "").lower() == "deceased":
        return _ROW_COLORS["deceased"]
    return None


def _action_btn(label: str, callback) -> QPushButton:
    btn = QPushButton(label)
    btn.setFixedHeight(22)
    btn.setFixedWidth(52)
    btn.clicked.connect(callback)
    return btn


class SubjectsTab(QWidget):
    open_subject_detail = Signal(object)
    create_subject_requested = Signal()

    _COLS = ["#", "Name", "Type", "Status", "LKP / Context", "Age", "Updated", "Actions"]

    def __init__(self, service: IntelService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._subjects: list[Subject] = []
        self._filtered: list[Subject] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()
        title = QLabel("Subjects")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: palette(windowText);")

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search…")
        self._search.setFixedWidth(200)
        self._search.textChanged.connect(self._apply_filter)

        self._type_filter = QComboBox()
        self._type_filter.addItem("All Types")
        self._type_filter.addItems(SUBJECT_TYPES)
        self._type_filter.currentTextChanged.connect(self._apply_filter)

        self._status_filter = QComboBox()
        self._status_filter.addItems(["All Statuses", "Active", "Located", "Deceased", "Archived"])
        self._status_filter.currentTextChanged.connect(self._apply_filter)

        new_btn = QPushButton("+ New Subject")
        new_btn.clicked.connect(self.create_subject_requested)

        toolbar.addWidget(title)
        toolbar.addStretch()
        toolbar.addWidget(self._search)
        toolbar.addWidget(self._type_filter)
        toolbar.addWidget(self._status_filter)
        toolbar.addWidget(new_btn)
        layout.addLayout(toolbar)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        self._table = QTableWidget()
        self._table.setColumnCount(len(self._COLS))
        self._table.setHorizontalHeaderLabels(self._COLS)
        apply_statusboard_table_behavior(self._table)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setSortingEnabled(True)
        self._table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)

        self.refresh()

    def refresh(self) -> None:
        if self._service is None:
            return
        self._subjects = self._service.subjects.list()
        self._apply_filter()

    def _apply_filter(self) -> None:
        q = self._search.text().lower()
        type_sel = self._type_filter.currentText()
        status_sel = self._status_filter.currentText()
        self._filtered = [
            s for s in self._subjects
            if (not q or q in (s.name or "").lower() or q in (s.lkp_place or "").lower())
            and (type_sel == "All Types" or s.subject_type == type_sel)
            and (status_sel == "All Statuses" or s.status == status_sel)
        ]
        self._render()

    def _render(self) -> None:
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(self._filtered))
        for row, s in enumerate(self._filtered):
            context = ""
            if s.subject_type == SubjectType.MISSING_PERSON and s.lkp_place:
                context = f"LKP: {s.lkp_place}"
            elif s.phone:
                context = s.phone
            elif s.organization:
                context = s.organization

            cells = [
                str(row + 1), s.name or "", s.subject_type or "", s.status or "",
                context, str(s.age) if s.age else "",
                s.updated_at[:16].replace("T", " ") if s.updated_at else "",
            ]
            color = _row_color(s)
            brush = QBrush(color) if color else None
            for col, val in enumerate(cells):
                item = QTableWidgetItem(val)
                if brush:
                    item.setBackground(brush)
                self._table.setItem(row, col, item)

            # Actions widget
            actions = QWidget()
            al = QHBoxLayout(actions)
            al.setContentsMargins(4, 2, 4, 2)
            al.setSpacing(4)
            subject = s  # capture
            al.addWidget(_action_btn("View", lambda _, x=subject: self.open_subject_detail.emit(x)))
            self._table.setCellWidget(row, len(self._COLS) - 1, actions)
            self._table.setRowHeight(row, 30)

        for col in (0, 2, 3, 5, 6):
            self._table.resizeColumnToContents(col)
        self._table.setColumnWidth(len(self._COLS) - 1, 70)
        self._table.setSortingEnabled(True)

    def _on_double_click(self, index) -> None:
        col = index.column()
        row = index.row()
        if col < len(self._COLS) - 1 and 0 <= row < len(self._filtered):
            self.open_subject_detail.emit(self._filtered[row])
