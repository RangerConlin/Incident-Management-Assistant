"""AssessmentsTab — table view for Intel analytical products."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QDialog, QFormLayout,
    QTextEdit, QDialogButtonBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush

from modules.intel.models.assessments import Assessment, AssessmentStatus, ASSESSMENT_STATUSES
from modules.intel.services.intel_service import IntelService
from utils.table_view_styles import apply_statusboard_table_behavior
from utils.styles import intel_assessment_status_colors, get_palette, subscribe_theme


def _color_blob(hex_color: str, label: str) -> str:
    return (
        f'<span style="color: {hex_color}; font-size: 16px; vertical-align: middle;">&#9679;</span> '
        f'<span style="vertical-align: middle;">{label}</span>'
    )


def _row_color(a: Assessment) -> QBrush | None:
    colors = intel_assessment_status_colors()
    status = colors.get((a.status or "").lower())
    return status["bg"] if status else None


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
        self._summary.setPlaceholderText(
            "Brief analytical summary — what question or situation is this assessment addressing?"
        )
        self._summary.setMinimumHeight(80)
        form.addRow("Summary", self._summary)

        self._findings = QTextEdit()
        self._findings.setPlaceholderText("What the available Intel records indicate")
        self._findings.setMinimumHeight(60)
        form.addRow("Findings", self._findings)

        self._recommendations = QTextEdit()
        self._recommendations.setPlaceholderText(
            "Recommended actions or considerations for planning/command"
        )
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
            self._title.setStyleSheet(f"border: 1px solid {get_palette()['error'].name()};")
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

        subtitle = QLabel("Analytical products — findings and recommendations from linked Intel records")
        subtitle.setStyleSheet("color: palette(placeholderText); font-size: 12px;")
        layout.addWidget(subtitle)

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
        self._legend = QLabel()
        self._legend.setTextFormat(Qt.RichText)
        self._legend.setStyleSheet("font-size: 11px; color: palette(placeholderText);")
        layout.addWidget(self._legend)
        self._update_legend()

        subscribe_theme(self, self._on_theme_changed)
        self.refresh()

    def _update_legend(self) -> None:
        colors = intel_assessment_status_colors()
        self._legend.setText(
            "  ".join([
                _color_blob(colors["draft"]["fg"].color().name(), "Draft"),
                _color_blob(colors["in progress"]["fg"].color().name(), "In Progress"),
                _color_blob(colors["complete"]["fg"].color().name(), "Complete"),
                _color_blob(colors["archived"]["fg"].color().name(), "Archived"),
            ])
        )

    def _on_theme_changed(self, *_: object) -> None:
        self._update_legend()
        self._render()

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
            brush = _row_color(a)
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
