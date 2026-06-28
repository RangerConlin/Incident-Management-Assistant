"""LeadsTab — table view for Intel leads."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QDialog, QFormLayout,
    QTextEdit, QDialogButtonBox, QInputDialog,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush

from modules.intel.models.leads import (
    Lead, LeadStatus, LeadPriority, LEAD_STATUSES, LEAD_PRIORITIES, LEAD_SOURCE_TYPES,
)
from modules.intel.services.intel_service import IntelService
from utils.table_view_styles import apply_statusboard_table_behavior

_ROW_COLORS: dict[str, QColor] = {
    "unassigned_high":   QColor(180, 40,  40,  130),
    "unassigned":        QColor(180, 100, 20,  110),
    "new":               QColor(30,  80,  180, 100),
    "assigned":          QColor(20,  100, 160, 90),
    "converted":         QColor(40,  160, 80,  100),
    "closed":            QColor(100, 100, 100, 75),
}


def _row_color(lead: Lead) -> QColor | None:
    status = (lead.status or "").lower()
    if not lead.assigned_to and lead.priority in ("Critical", "High"):
        return _ROW_COLORS["unassigned_high"]
    if not lead.assigned_to:
        return _ROW_COLORS["unassigned"]
    return _ROW_COLORS.get(status)


def _btn(label: str, callback, width: int = 52) -> QPushButton:
    b = QPushButton(label)
    b.setFixedHeight(22)
    b.setFixedWidth(width)
    b.clicked.connect(callback)
    return b


class _NewLeadDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Lead")
        self.setMinimumWidth(460)
        self.lead: Lead | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(8)

        self._title = QLineEdit()
        self._title.setPlaceholderText("Brief description (required)")
        form.addRow("Title *", self._title)

        self._summary = QTextEdit()
        self._summary.setPlaceholderText("Detailed summary")
        self._summary.setMinimumHeight(60)
        form.addRow("Summary", self._summary)

        self._source = QComboBox()
        self._source.addItems(LEAD_SOURCE_TYPES)
        form.addRow("Source Type", self._source)

        self._reported_by = QLineEdit()
        form.addRow("Reported By", self._reported_by)

        self._contact = QLineEdit()
        self._contact.setPlaceholderText("Phone, email, or other")
        form.addRow("Contact Info", self._contact)

        self._location = QLineEdit()
        form.addRow("Location", self._location)

        self._priority = QComboBox()
        self._priority.addItems(LEAD_PRIORITIES)
        self._priority.setCurrentText(LeadPriority.MEDIUM)
        form.addRow("Priority", self._priority)

        self._assigned_to = QLineEdit()
        self._assigned_to.setPlaceholderText("Leave blank if unassigned")
        form.addRow("Assign To", self._assigned_to)

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
        self.lead = Lead(
            id="", incident_id="",
            title=title,
            summary=self._summary.toPlainText().strip(),
            source_type=self._source.currentText(),
            reported_by=self._reported_by.text().strip(),
            contact_info=self._contact.text().strip() or None,
            location_text=self._location.text().strip() or None,
            priority=self._priority.currentText(),
            assigned_to=self._assigned_to.text().strip() or None,
        )
        self.accept()


class LeadsTab(QWidget):
    open_lead_detail = Signal(object)
    convert_lead = Signal(object)

    _COLS = ["#", "Title", "Priority", "Status", "Source", "Assigned To", "Updated", "Actions"]

    def __init__(self, service: IntelService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._leads: list[Lead] = []
        self._filtered: list[Lead] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()
        title = QLabel("Leads")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: palette(windowText);")

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search…")
        self._search.setFixedWidth(200)
        self._search.textChanged.connect(self._apply_filter)

        self._status_filter = QComboBox()
        self._status_filter.addItem("All Statuses")
        self._status_filter.addItems(LEAD_STATUSES)
        self._status_filter.currentTextChanged.connect(self._apply_filter)

        self._priority_filter = QComboBox()
        self._priority_filter.addItem("All Priorities")
        self._priority_filter.addItems(LEAD_PRIORITIES)
        self._priority_filter.currentTextChanged.connect(self._apply_filter)

        new_btn = QPushButton("+ New Lead")
        new_btn.clicked.connect(self._new_lead)

        toolbar.addWidget(title)
        toolbar.addStretch()
        toolbar.addWidget(self._search)
        toolbar.addWidget(self._status_filter)
        toolbar.addWidget(self._priority_filter)
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
        self._table.verticalHeader().setVisible(False)
        self._table.setSortingEnabled(True)
        self._table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)

        self.refresh()

    def refresh(self) -> None:
        if self._service is None:
            return
        self._leads = self._service.leads.list()
        self._apply_filter()

    def _apply_filter(self) -> None:
        q = self._search.text().lower()
        status_sel = self._status_filter.currentText()
        priority_sel = self._priority_filter.currentText()
        self._filtered = [
            l for l in self._leads
            if (not q or q in l.title.lower() or q in (l.summary or "").lower())
            and (status_sel == "All Statuses" or l.status == status_sel)
            and (priority_sel == "All Priorities" or l.priority == priority_sel)
        ]
        self._render()

    def _render(self) -> None:
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(self._filtered))
        for row, l in enumerate(self._filtered):
            cells = [
                l.display_number, l.title, l.priority or "", l.status or "",
                l.source_type or "", l.assigned_to or "Unassigned",
                l.updated_at[:16].replace("T", " ") if l.updated_at else "",
            ]
            color = _row_color(l)
            brush = QBrush(color) if color else None
            for col, val in enumerate(cells):
                item = QTableWidgetItem(val)
                if brush:
                    item.setBackground(brush)
                self._table.setItem(row, col, item)

            actions = QWidget()
            al = QHBoxLayout(actions)
            al.setContentsMargins(4, 2, 4, 2)
            al.setSpacing(3)
            lead = l
            al.addWidget(_btn("View",   lambda _, x=lead: self.open_lead_detail.emit(x), width=52))
            al.addWidget(_btn("Assign", lambda _, x=lead: self._assign_lead(x), width=60))
            al.addWidget(_btn("→ Item", lambda _, x=lead: self.convert_lead.emit(x), width=62))
            self._table.setCellWidget(row, len(self._COLS) - 1, actions)
            self._table.setRowHeight(row, 30)

        for col in (0, 2, 3, 4, 5, 6):
            self._table.resizeColumnToContents(col)
        self._table.setColumnWidth(len(self._COLS) - 1, 190)
        self._table.setSortingEnabled(True)

    def _on_double_click(self, index) -> None:
        col, row = index.column(), index.row()
        if col < len(self._COLS) - 1 and 0 <= row < len(self._filtered):
            self.open_lead_detail.emit(self._filtered[row])

    def _new_lead(self) -> None:
        if self._service is None:
            return
        dlg = _NewLeadDialog(self)
        if dlg.exec() == QDialog.Accepted and dlg.lead:
            self._service.leads.create(dlg.lead)
            self.refresh()

    def _assign_lead(self, lead: Lead) -> None:
        if self._service is None:
            return
        name, ok = QInputDialog.getText(
            self, "Assign Lead", f"Assign {lead.display_number} to:",
            text=lead.assigned_to or "",
        )
        if ok:
            self._service.leads.update(lead.id, {
                "assigned_to": name.strip() or None,
                "status": LeadStatus.ASSIGNED if name.strip() else lead.status,
            })
            self.refresh()
