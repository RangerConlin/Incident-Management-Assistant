"""Dashboard panel for Safety Incident (IWI) reports — table view with drill-down."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules.safety import services
from modules.safety.panels.iwi_detail_dialog import IWIDetailDialog

SEVERITY_COLORS = {
    "MINOR": ("#e8f5e9", "#2e7d32"),
    "MODERATE": ("#fff3e0", "#e65100"),
    "SERIOUS": ("#ffebee", "#b71c1c"),
    "CRITICAL": ("#f3e5f5", "#4a148c"),
}

STATUS_COLORS = {
    "draft": "#546e7a",
    "submitted": "#1565c0",
    "reviewed": "#e65100",
    "closed": "#2e7d32",
}

COLUMNS = ["Form #", "Date", "Time", "Type(s)", "Severity", "Location", "Persons", "Status"]


class IWIDashboard(QWidget):
    """Main dashboard listing all Safety Incident reports for an incident."""

    def __init__(self, incident_id: str, parent=None):
        super().__init__(parent)
        self._incident_id = incident_id
        self._reports: list[dict] = []
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 8)
        layout.setSpacing(8)

        # Header row
        header_row = QHBoxLayout()
        title = QLabel("Safety Incident Reports")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        header_row.addWidget(title)
        header_row.addStretch()

        # Filters
        self._severity_filter = QComboBox()
        self._severity_filter.addItems(["All Severities", "MINOR", "MODERATE", "SERIOUS", "CRITICAL"])
        self._severity_filter.currentTextChanged.connect(self._load)

        self._status_filter = QComboBox()
        self._status_filter.addItems(["All Statuses", "draft", "submitted", "reviewed", "closed"])
        self._status_filter.currentTextChanged.connect(self._load)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._load)

        new_btn = QPushButton("+ New Report")
        new_btn.setStyleSheet(
            "background-color: #1a237e; color: white; font-weight: 600; padding: 4px 12px; border-radius: 4px;"
        )
        new_btn.clicked.connect(self._new_report)

        header_row.addWidget(QLabel("Severity:"))
        header_row.addWidget(self._severity_filter)
        header_row.addWidget(QLabel("Status:"))
        header_row.addWidget(self._status_filter)
        header_row.addWidget(refresh_btn)
        header_row.addWidget(new_btn)
        layout.addLayout(header_row)

        # Table
        self._table = QTableWidget(0, len(COLUMNS))
        self._table.setHorizontalHeaderLabels(COLUMNS)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.setWordWrap(False)
        self._table.doubleClicked.connect(self._open_selected)
        layout.addWidget(self._table, 1)

        # Bottom action row
        action_row = QHBoxLayout()
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet("color: #666; font-size: 11px;")
        open_btn = QPushButton("Open")
        open_btn.clicked.connect(self._open_selected)
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_selected)
        action_row.addWidget(self._count_lbl)
        action_row.addStretch()
        action_row.addWidget(open_btn)
        action_row.addWidget(delete_btn)
        layout.addLayout(action_row)

    def _load(self) -> None:
        sev = self._severity_filter.currentText()
        stat = self._status_filter.currentText()
        kwargs = {}
        if sev != "All Severities":
            kwargs["severity"] = sev
        if stat != "All Statuses":
            kwargs["status"] = stat
        self._reports = services.list_iwi_reports(self._incident_id, **kwargs)
        self._refresh_table()

    def _refresh_table(self) -> None:
        self._table.setRowCount(len(self._reports))
        for row, r in enumerate(self._reports):
            self._table.setItem(row, 0, QTableWidgetItem(str(r.get("form_number") or "")))
            self._table.setItem(row, 1, QTableWidgetItem(r.get("date_of_occurrence") or ""))
            self._table.setItem(row, 2, QTableWidgetItem(r.get("time_of_occurrence") or ""))
            types = r.get("incident_types") or []
            self._table.setItem(row, 3, QTableWidgetItem(", ".join(types)))

            # Severity chip via background color
            sev = r.get("actual_severity") or ""
            sev_item = QTableWidgetItem(sev)
            sev_item.setTextAlignment(Qt.AlignCenter)
            bg, fg = SEVERITY_COLORS.get(sev, ("#f5f5f5", "#333"))
            from PySide6.QtGui import QColor, QBrush
            sev_item.setBackground(QBrush(QColor(bg)))
            sev_item.setForeground(QBrush(QColor(fg)))
            self._table.setItem(row, 4, sev_item)

            self._table.setItem(row, 5, QTableWidgetItem(r.get("location_general") or ""))
            persons = r.get("persons_involved") or []
            self._table.setItem(row, 6, QTableWidgetItem(str(len(persons))))

            status = r.get("status") or "draft"
            status_item = QTableWidgetItem(status.title())
            status_item.setTextAlignment(Qt.AlignCenter)
            status_color = STATUS_COLORS.get(status, "#546e7a")
            status_item.setForeground(QBrush(QColor(status_color)))
            self._table.setItem(row, 7, status_item)

        self._table.resizeColumnsToContents()
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        n = len(self._reports)
        self._count_lbl.setText(f"{n} report{'s' if n != 1 else ''}")

    def _selected_report(self) -> Optional[dict]:
        row = self._table.currentRow()
        if 0 <= row < len(self._reports):
            return self._reports[row]
        return None

    def _open_selected(self) -> None:
        report = self._selected_report()
        report_id = report.get("_id") if report else None
        dlg = IWIDetailDialog(self._incident_id, report_id=report_id, parent=self)
        dlg.exec()
        self._load()

    def _new_report(self) -> None:
        dlg = IWIDetailDialog(self._incident_id, parent=self)
        dlg.exec()
        self._load()

    def _delete_selected(self) -> None:
        report = self._selected_report()
        if not report:
            return
        fn = report.get("form_number", "")
        if (
            QMessageBox.question(
                self,
                "Delete Report",
                f"Delete Safety Incident Report #{fn}?",
            )
            == QMessageBox.Yes
        ):
            rid = report.get("_id")
            if rid:
                services.delete_iwi_report(self._incident_id, rid)
            self._load()
