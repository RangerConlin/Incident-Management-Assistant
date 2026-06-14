from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from . import services
from .records import PlannedRecord, PlannedToolDefinition, ScheduledItem, TOOLS
from .widgets.schedule_widget import ScheduleWidget

__all__ = [
    "get_promotions_panel",
    "get_vendors_panel",
    "get_permits_panel",
    "get_safety_panel",
    "get_tasking_panel",
    "get_health_sanitation_panel",
    "get_planned_toolkit_panel",
]


class _BaseToolPanel(QWidget):
    def __init__(
        self,
        tool: PlannedToolDefinition,
        incident_id: object | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.tool = tool
        self.incident_id = None if incident_id is None else str(incident_id)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        title = QLabel(self.tool.label)
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.status_label)
        layout.addLayout(header)

        form = QFormLayout()
        self.title_edit = QLineEdit()
        self.summary_edit = QTextEdit()
        self.summary_edit.setFixedHeight(70)
        self.status_edit = QLineEdit(self.tool.default_status)
        self.priority_edit = QLineEdit(self.tool.default_priority)
        self.assigned_edit = QLineEdit()
        self.location_edit = QLineEdit()
        self.scheduled_edit = QLineEdit()
        self.due_edit = QLineEdit()
        self.metadata_edit = QLineEdit()
        form.addRow(self.tool.title_label, self.title_edit)
        form.addRow(self.tool.summary_label, self.summary_edit)
        form.addRow("Status", self.status_edit)
        form.addRow("Priority", self.priority_edit)
        form.addRow("Assigned To", self.assigned_edit)
        form.addRow("Location", self.location_edit)
        form.addRow("Scheduled", self.scheduled_edit)
        form.addRow("Due", self.due_edit)
        form.addRow("Metadata JSON", self.metadata_edit)
        layout.addLayout(form)

        actions = QHBoxLayout()
        add_btn = QPushButton("Add")
        refresh_btn = QPushButton("Refresh")
        add_btn.clicked.connect(self.add_record)
        refresh_btn.clicked.connect(self.refresh)
        actions.addWidget(add_btn)
        actions.addWidget(refresh_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["ID", self.tool.title_label, "Status", "Priority", "Assigned", "Location", "Updated"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

    def _iid(self) -> str | None:
        return self.incident_id

    def _set_status(self, message: str, *, error: bool = False) -> None:
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {'#b00020' if error else '#375a2b'};")

    def refresh(self) -> None:
        if not self._iid():
            self.table.setRowCount(0)
            self._set_status("Select an incident to use this panel.", error=True)
            return
        try:
            rows = services.list_records(self.tool.key, self._iid())
        except Exception as exc:
            self.table.setRowCount(0)
            self._set_status(str(exc), error=True)
            return
        self._populate(rows)
        self._set_status(f"{len(rows)} records")

    def add_record(self) -> None:
        if not self._iid():
            self._set_status("Select an incident before creating records.", error=True)
            return
        title = self.title_edit.text().strip()
        if not title:
            self._set_status(f"{self.tool.title_label} is required", error=True)
            return
        metadata: dict[str, object] = {}
        raw_metadata = self.metadata_edit.text().strip()
        if raw_metadata:
            metadata["raw"] = raw_metadata
        try:
            services.create_record(
                self.tool.key,
                self._iid(),
                title=title,
                summary=self.summary_edit.toPlainText().strip(),
                status=self.status_edit.text().strip() or self.tool.default_status,
                priority=self.priority_edit.text().strip(),
                assigned_to=self.assigned_edit.text().strip(),
                location=self.location_edit.text().strip(),
                scheduled_at=self.scheduled_edit.text().strip(),
                due_at=self.due_edit.text().strip(),
                metadata=metadata,
            )
        except Exception as exc:
            self._set_status(str(exc), error=True)
            return
        self.title_edit.clear()
        self.summary_edit.clear()
        self.metadata_edit.clear()
        self.refresh()

    def _populate(self, rows: Iterable[PlannedRecord]) -> None:
        records = list(rows)
        self.table.setRowCount(len(records))
        for row_idx, record in enumerate(records):
            values = [
                record.id,
                record.title,
                record.status,
                record.priority,
                record.assigned_to,
                record.location,
                record.updated_at or record.created_at,
            ]
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem("" if value is None else str(value))
                if col_idx == 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row_idx, col_idx, item)


class PromotionsPanel(QWidget):
    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(_BaseToolPanel(TOOLS["promotions"], incident_id), "Campaigns")
        tabs.addTab(ScheduleWidget(incident_id), "Schedule")
        layout.addWidget(tabs)


class PlannedToolkitHome(QWidget):
    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(PromotionsPanel(incident_id), "Promotions")
        for key in ("vendors", "permits", "safety-reports", "tasks", "health-inspections"):
            tabs.addTab(_BaseToolPanel(TOOLS[key], incident_id), TOOLS[key].label)
        layout.addWidget(tabs)


def get_promotions_panel(incident_id: object | None = None) -> QWidget:
    return PromotionsPanel(incident_id)


def get_vendors_panel(incident_id: object | None = None) -> QWidget:
    return _BaseToolPanel(TOOLS["vendors"], incident_id)


def get_permits_panel(incident_id: object | None = None) -> QWidget:
    return _BaseToolPanel(TOOLS["permits"], incident_id)


def get_safety_panel(incident_id: object | None = None) -> QWidget:
    return _BaseToolPanel(TOOLS["safety-reports"], incident_id)


def get_tasking_panel(incident_id: object | None = None) -> QWidget:
    return _BaseToolPanel(TOOLS["tasks"], incident_id)


def get_health_sanitation_panel(incident_id: object | None = None) -> QWidget:
    return _BaseToolPanel(TOOLS["health-inspections"], incident_id)


def get_planned_toolkit_panel(incident_id: object | None = None) -> QWidget:
    return PlannedToolkitHome(incident_id)
