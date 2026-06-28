from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from utils.table_view_styles import apply_statusboard_table_behavior


def _section_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet("font-size: 13px; font-weight: 600;")
    return label


class DemobilizationPanel(QWidget):
    """Planning-side demobilization board."""

    def __init__(self, incident_id: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._incident_id = incident_id
        self.setObjectName("PlanningDemobilizationPanel")
        self.setWindowTitle("Planning - Demobilization")
        self.resize(1100, 720)
        self._build_ui()
        self._load_seed_content()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Demobilization Planner")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        header.addWidget(title)
        header.addStretch()
        incident_text = self._incident_id or "No active incident"
        self._incident_badge = QLabel(f"Incident: {incident_text}")
        self._incident_badge.setStyleSheet(
            "padding: 4px 10px; border-radius: 10px; background: palette(base); font-weight: 600;"
        )
        header.addWidget(self._incident_badge)
        root.addLayout(header)

        summary = QFrame()
        summary.setObjectName("DemobSummary")
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(12, 10, 12, 10)
        summary_layout.setSpacing(14)
        for label, value in (
            ("Release Candidates", "12"),
            ("Blocked Releases", "3"),
            ("Travel / Return Plans", "5 Pending"),
            ("ICS-221 Readiness", "Needs Review"),
        ):
            cell = QVBoxLayout()
            count = QLabel(value)
            count.setAlignment(Qt.AlignCenter)
            count.setStyleSheet("font-size: 18px; font-weight: 700;")
            name = QLabel(label)
            name.setAlignment(Qt.AlignCenter)
            name.setWordWrap(True)
            cell.addWidget(count)
            cell.addWidget(name)
            summary_layout.addLayout(cell, 1)
        root.addWidget(summary)

        middle = QHBoxLayout()
        middle.setSpacing(10)

        priorities_group = QGroupBox("Demobilization Priorities")
        priorities_layout = QVBoxLayout(priorities_group)
        priorities_layout.addWidget(_section_title("Section focus for the next operational period"))
        self._priorities_list = QListWidget()
        priorities_layout.addWidget(self._priorities_list)
        priorities_buttons = QHBoxLayout()
        for text in ("Open ICS-221", "Review Release Queue", "Export Demob Brief"):
            priorities_buttons.addWidget(QPushButton(text))
        priorities_layout.addLayout(priorities_buttons)

        checklist_group = QGroupBox("Planning Checklist")
        checklist_layout = QVBoxLayout(checklist_group)
        checklist_layout.addWidget(_section_title("Core demob planning steps"))
        self._checklist_list = QListWidget()
        checklist_layout.addWidget(self._checklist_list)

        middle.addWidget(priorities_group, 1)
        middle.addWidget(checklist_group, 1)
        root.addLayout(middle)

        table_group = QGroupBox("Release Board")
        table_layout = QVBoxLayout(table_group)
        table_layout.addWidget(_section_title("Resources and teams nearing release"))
        self._release_table = QTableWidget(0, 5)
        self._release_table.setHorizontalHeaderLabels(
            ["Resource", "Assignment", "Release Window", "Dependencies", "Status"]
        )
        apply_statusboard_table_behavior(self._release_table, stretch_last_section=True)
        table_layout.addWidget(self._release_table)
        root.addWidget(table_group, 1)

        closeout_group = QGroupBox("Closeout Notes")
        closeout_layout = QVBoxLayout(closeout_group)
        closeout_layout.addWidget(_section_title("Demob issues to capture in the next planning cycle"))
        self._closeout_list = QListWidget()
        closeout_layout.addWidget(self._closeout_list)
        root.addWidget(closeout_group)

        self.setStyleSheet(
            """
            QFrame#DemobSummary {
                border: 1px solid #d9dee5;
                border-radius: 10px;
                background: #fafbfc;
            }
            QGroupBox {
                font-weight: 600;
            }
            QListWidget, QTableWidget {
                background: #ffffff;
                border: 1px solid #d9dee5;
                border-radius: 6px;
            }
            QPushButton {
                padding: 4px 10px;
            }
            """
        )

    def _load_seed_content(self) -> None:
        self._populate_list(
            self._priorities_list,
            (
                "Confirm release priorities with Operations and Logistics before end-of-shift briefing.",
                "Identify resources that can be released within 12 hours without impacting life-safety coverage.",
                "Verify transportation, rehab, and documentation requirements for outbound personnel.",
                "Flag any crews or equipment that must remain on contingency status through the next operational period.",
            ),
        )
        self._populate_list(
            self._checklist_list,
            (
                "Establish demobilization criteria tied to incident objectives and control benchmarks.",
                "Publish unit-by-unit release sequence and required supervisor approvals.",
                "Coordinate ICS-221 completion, timekeeping, and property/accountability sign-off.",
                "Capture return-travel instructions, staging, and destination routing.",
                "Document residual risks, follow-on monitoring, and reactivation triggers.",
            ),
        )
        self._populate_release_rows(
            (
                ("Task Force 1", "Perimeter support", "Today 1800-2000", "Fuel, time audit, briefing", "Ready"),
                ("MED-2", "Base medical standby", "Today 2000", "Replacement EMS coverage", "Blocked"),
                ("Dozer 7", "Debris clearance", "Tomorrow 0600", "Transport trailer", "Pending"),
                ("Comms Trailer", "ICP support", "Tomorrow 0900", "Frequency plan archive", "In Review"),
            )
        )
        self._populate_list(
            self._closeout_list,
            (
                "Need a formal trigger for partial demob versus full incident transition.",
                "Finance closeout and equipment return steps should be confirmed in the demob brief.",
                "Logistics already surfaces a demob queue; Planning should keep the release sequence aligned.",
            ),
        )

    def _populate_list(self, widget: QListWidget, rows: Iterable[str]) -> None:
        widget.clear()
        for row in rows:
            QListWidgetItem(row, widget)

    def _populate_release_rows(self, rows: Iterable[tuple[str, str, str, str, str]]) -> None:
        self._release_table.setRowCount(0)
        for row_idx, row in enumerate(rows):
            self._release_table.insertRow(row_idx)
            for col_idx, value in enumerate(row):
                item = QTableWidgetItem(value)
                if col_idx == 4:
                    item.setBackground(self._status_color(value))
                self._release_table.setItem(row_idx, col_idx, item)

    def _status_color(self, status: str) -> QColor:
        lowered = status.strip().lower()
        if lowered == "ready":
            return QColor("#e8f5e9")
        if lowered == "blocked":
            return QColor("#ffebee")
        if lowered == "pending":
            return QColor("#fff8e1")
        return QColor("#eceff1")


def make_demobilization_panel(
    incident_id: str | None = None,
    parent: QWidget | None = None,
) -> DemobilizationPanel:
    return DemobilizationPanel(incident_id=incident_id, parent=parent)


__all__ = ["DemobilizationPanel", "make_demobilization_panel"]
