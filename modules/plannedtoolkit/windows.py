from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGridLayout,
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

from utils.api_client import APIError

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


@dataclass(frozen=True)
class PanelSpec:
    title: str
    tool_key: str
    columns: tuple[str, ...]
    extra_rows: tuple[tuple[str, str], ...] = ()


PROMOTION_SPEC = PanelSpec(
    title="Campaigns",
    tool_key="promotions",
    columns=("ID", "Campaign", "Status", "Audience", "Channel", "Updated"),
    extra_rows=(("Audience", "assigned_edit"), ("Channel", "location_edit")),
)

VENDOR_SPEC = PanelSpec(
    title="Vendors",
    tool_key="vendors",
    columns=("ID", "Vendor", "Status", "Contact", "Location", "Updated"),
)

PERMIT_SPEC = PanelSpec(
    title="Permits",
    tool_key="permits",
    columns=("ID", "Permit", "Status", "Issued By", "Expiry", "Updated"),
)

SAFETY_SPEC = PanelSpec(
    title="Safety",
    tool_key="safety-reports",
    columns=("ID", "Report", "Status", "Priority", "Location", "Updated"),
    extra_rows=(("Location", "location_edit"),),
)

TASK_SPEC = PanelSpec(
    title="Quick Assignments",
    tool_key="quick-assignments",
    columns=("ID", "Assignment", "Status", "Priority", "Assignee", "Due", "Updated"),
    extra_rows=(("Assignee", "assigned_edit"), ("Due", "due_edit")),
)

HEALTH_SPEC = PanelSpec(
    title="Health & Sanitation",
    tool_key="health-inspections",
    columns=("ID", "Inspection", "Status", "Target", "Updated"),
)


class _ToolPanel(QWidget):
    def __init__(self, spec: PanelSpec, incident_id: object | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.spec = spec
        self.tool = TOOLS[spec.tool_key]
        self.incident_id = None if incident_id is None else str(incident_id)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        title = QLabel(self.spec.title)
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
        for label, attr in self.spec.extra_rows:
            form.addRow(label, getattr(self, attr))
        form.addRow("Status", self.status_edit)
        form.addRow("Priority", self.priority_edit)
        form.addRow("Location", self.location_edit)
        form.addRow("Scheduled", self.scheduled_edit)
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

        self.table = QTableWidget(0, len(self.spec.columns))
        self.table.setHorizontalHeaderLabels(list(self.spec.columns))
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

    def _iid(self) -> str | None:
        return self.incident_id

    def _set_status(self, message: str, *, error: bool = False) -> None:
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {'#b00020' if error else '#375a2b'};")

    def _describe_error(self, exc: Exception) -> str:
        if isinstance(exc, APIError):
            if exc.status_code is None:
                return f"{self.spec.title} API unavailable: {exc}"
            return f"{self.spec.title} API error {exc.status_code}: {exc}"
        return str(exc)

    def refresh(self) -> None:
        if not self._iid():
            self.table.setRowCount(0)
            self._set_status("Select an incident to use this panel.", error=True)
            return
        try:
            rows = services.list_records(self.spec.tool_key, self._iid())
        except Exception as exc:
            self.table.setRowCount(0)
            self._set_status(self._describe_error(exc), error=True)
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
                self.spec.tool_key,
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
            self._set_status(self._describe_error(exc), error=True)
            return
        self.title_edit.clear()
        self.summary_edit.clear()
        self.metadata_edit.clear()
        self.refresh()

    def _row_values(self, record: PlannedRecord) -> list[str]:
        if self.spec.tool_key == "promotions":
            return [
                str(record.id or ""),
                record.title,
                record.status,
                record.metadata.get("audience", record.assigned_to) if isinstance(record.metadata, dict) else record.assigned_to,
                record.metadata.get("channel", record.location) if isinstance(record.metadata, dict) else record.location,
                record.updated_at or record.created_at,
            ]
        if self.spec.tool_key == "vendors":
            return [str(record.id or ""), record.title, record.status, record.assigned_to, record.location, record.updated_at or record.created_at]
        if self.spec.tool_key == "permits":
            expiry = record.due_at or record.metadata.get("expires_on", "") if isinstance(record.metadata, dict) else record.due_at
            issuer = record.metadata.get("issuer", "") if isinstance(record.metadata, dict) else ""
            return [str(record.id or ""), record.title, record.status, issuer, expiry, record.updated_at or record.created_at]
        if self.spec.tool_key == "tasks":
            return [str(record.id or ""), record.title, record.status, record.priority, record.assigned_to, record.due_at, record.updated_at or record.created_at]
        if self.spec.tool_key == "health-inspections":
            target = record.location or record.assigned_to
            return [str(record.id or ""), record.title, record.status, target, record.updated_at or record.created_at]
        return [
            str(record.id or ""),
            record.title,
            record.status,
            record.priority,
            record.assigned_to,
            record.location,
            record.updated_at or record.created_at,
        ]

    def _populate(self, rows: Iterable[PlannedRecord]) -> None:
        records = list(rows)
        self.table.setRowCount(len(records))
        for row_idx, record in enumerate(records):
            values = self._row_values(record)
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem("" if value is None else str(value))
                if col_idx == 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row_idx, col_idx, item)


class _DashboardCard(QFrame):
    def __init__(self, heading: str, body: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("QFrame { border: 1px solid #d0d0d0; border-radius: 4px; padding: 6px; }")
        layout = QVBoxLayout(self)
        title = QLabel(heading)
        title.setStyleSheet("font-weight: 600;")
        label = QLabel(body)
        label.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(label)


class PromotionsPanel(QWidget):
    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(_ToolPanel(PROMOTION_SPEC, incident_id), "Campaigns")
        tabs.addTab(ScheduleWidget(incident_id), "Schedule")
        layout.addWidget(tabs)


class PlannedToolkitHome(QWidget):
    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        top = QGridLayout()
        top.addWidget(_DashboardCard("Promotions", "Campaigns and event timing."), 0, 0)
        top.addWidget(_DashboardCard("Vendors", "Onsite partners, locations, and compliance."), 0, 1)
        top.addWidget(_DashboardCard("Safety", "Incidents, dispatch, and response."), 1, 0)
        top.addWidget(_DashboardCard("Operations", "Tasks and follow-up tracking."), 1, 1)
        layout.addLayout(top)

        tabs = QTabWidget()
        tabs.addTab(PromotionsPanel(incident_id), "Promotions")
        tabs.addTab(_ToolPanel(VENDOR_SPEC, incident_id), "Vendors")
        tabs.addTab(_ToolPanel(PERMIT_SPEC, incident_id), "Permits")
        tabs.addTab(_ToolPanel(SAFETY_SPEC, incident_id), "Public Safety")
        tabs.addTab(_ToolPanel(TASK_SPEC, incident_id), "Tasking")
        tabs.addTab(_ToolPanel(HEALTH_SPEC, incident_id), "Health & Sanitation")
        layout.addWidget(tabs)


def get_promotions_panel(incident_id: object | None = None) -> QWidget:
    return PromotionsPanel(incident_id)


def get_vendors_panel(incident_id: object | None = None) -> QWidget:
    return _ToolPanel(VENDOR_SPEC, incident_id)


def get_permits_panel(incident_id: object | None = None) -> QWidget:
    return _ToolPanel(PERMIT_SPEC, incident_id)


def get_safety_panel(incident_id: object | None = None) -> QWidget:
    return _ToolPanel(SAFETY_SPEC, incident_id)


def get_tasking_panel(incident_id: object | None = None) -> QWidget:
    return _ToolPanel(TASK_SPEC, incident_id)


def get_health_sanitation_panel(incident_id: object | None = None) -> QWidget:
    return _ToolPanel(HEALTH_SPEC, incident_id)


def get_planned_toolkit_panel(incident_id: object | None = None) -> QWidget:
    return PlannedToolkitHome(incident_id)
