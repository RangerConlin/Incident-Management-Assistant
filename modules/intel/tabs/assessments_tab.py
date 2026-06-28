"""AssessmentsTab — table view for Intel analytical products."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QDialog, QFormLayout,
    QTextEdit, QDialogButtonBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush

from modules.intel.models.assessments import Assessment, AssessmentStatus, ASSESSMENT_STATUSES
from modules.intel.services.intel_service import IntelService
from utils.table_view_styles import apply_statusboard_table_behavior

_ROW_COLORS: dict[str, QColor] = {
    "draft":     QColor(30,  80,  180, 110),
    "finalized": QColor(40,  160, 80,  100),
    "archived":  QColor(100, 100, 100, 80),
}


def _row_color(a: Assessment) -> QColor | None:
    return _ROW_COLORS.get((a.status or "").lower())


def _btn(label: str, callback, width: int = 52) -> "QPushButton":
    b = QPushButton(label)
    b.setFixedHeight(22)
    b.setFixedWidth(width)
    b.clicked.connect(callback)
    return b


class _NewAssessmentDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Assessment")
        self.setMinimumWidth(500)
        self.assessment: Assessment | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(8)

        self._title = QLineEdit()
        self._title.setPlaceholderText("Assessment title (required)")
        form.addRow("Title *", self._title)

        self._summary = QTextEdit()
        self._summary.setPlaceholderText("Situation narrative and analytical findings")
        self._summary.setMinimumHeight(80)
        form.addRow("Summary", self._summary)

        self._findings = QTextEdit()
        self._findings.setPlaceholderText("Analytical findings")
        self._findings.setMinimumHeight(60)
        form.addRow("Findings", self._findings)

        self._recommendations = QTextEdit()
        self._recommendations.setPlaceholderText("Recommended actions")
        self._recommendations.setMinimumHeight(60)
        form.addRow("Recommendations", self._recommendations)

        self._analyst = QLineEdit()
        form.addRow("Analyst", self._analyst)

        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_save(self) -> None:
        title = self._title.text().strip()
        if not title:
            self._title.setStyleSheet("border: 1px solid #cf222e;")
            return
        self.assessment = Assessment(
            id="", incident_id="",
            title=title,
            summary=self._summary.toPlainText().strip() or None,
            findings=self._findings.toPlainText().strip() or None,
            recommendations=self._recommendations.toPlainText().strip() or None,
            analyst=self._analyst.text().strip() or None,
        )
        self.accept()


class AssessmentsTab(QWidget):
    open_assessment_detail = Signal(object)

    _COLS = ["#", "Title", "Status", "Analyst", "Findings (excerpt)", "Updated", "Actions"]

    def __init__(self, service: IntelService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._assessments: list[Assessment] = []
        self._filtered: list[Assessment] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()
        title = QLabel("Assessments")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: palette(windowText);")

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search…")
        self._search.setFixedWidth(200)
        self._search.textChanged.connect(self._apply_filter)

        self._status_filter = QComboBox()
        self._status_filter.addItem("All Statuses")
        self._status_filter.addItems(ASSESSMENT_STATUSES)
        self._status_filter.currentTextChanged.connect(self._apply_filter)

        new_btn = QPushButton("+ New Assessment")
        new_btn.clicked.connect(self._new_assessment)

        toolbar.addWidget(title)
        toolbar.addStretch()
        toolbar.addWidget(self._search)
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
        self._assessments = self._service.assessments.list()
        self._apply_filter()

    def _apply_filter(self) -> None:
        q = self._search.text().lower()
        status_sel = self._status_filter.currentText()
        self._filtered = [
            a for a in self._assessments
            if (not q or q in a.title.lower() or q in (a.summary or "").lower())
            and (status_sel == "All Statuses" or a.status == status_sel)
        ]
        self._render()

    def _render(self) -> None:
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(self._filtered))
        for row, a in enumerate(self._filtered):
            findings_excerpt = (a.findings or "")[:120].replace("\n", " ")
            if a.findings and len(a.findings) > 120:
                findings_excerpt += "…"
            cells = [
                a.display_number,
                a.title,
                a.status or "",
                a.analyst or "",
                findings_excerpt,
                a.updated_at[:16].replace("T", " ") if a.updated_at else "",
            ]
            color = _row_color(a)
            brush = QBrush(color) if color else None
            for col, val in enumerate(cells):
                ti = QTableWidgetItem(val)
                if brush:
                    ti.setBackground(brush)
                self._table.setItem(row, col, ti)

            actions = QWidget()
            al = QHBoxLayout(actions)
            al.setContentsMargins(4, 2, 4, 2)
            al.setSpacing(4)
            assessment = a
            al.addWidget(_btn("View", lambda _, x=assessment: self.open_assessment_detail.emit(x)))
            self._table.setCellWidget(row, len(self._COLS) - 1, actions)
            self._table.setRowHeight(row, 30)

        for col in (0, 2, 3, 5):
            self._table.resizeColumnToContents(col)
        self._table.setColumnWidth(len(self._COLS) - 1, 70)
        self._table.setSortingEnabled(True)

    def _on_double_click(self, index) -> None:
        col, row = index.column(), index.row()
        if col < len(self._COLS) - 1 and 0 <= row < len(self._filtered):
            self.open_assessment_detail.emit(self._filtered[row])

    def _new_assessment(self) -> None:
        if self._service is None:
            return
        dlg = _NewAssessmentDialog(self)
        if dlg.exec() == QDialog.Accepted and dlg.assessment:
            self._service.assessments.create(dlg.assessment)
            self.refresh()
