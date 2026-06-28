from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
from utils.table_view_styles import apply_statusboard_table_behavior

from . import services
from .records import PlannedRecord, PlannedToolDefinition, ScheduledItem, TOOLS
from .widgets.schedule_widget import ScheduleWidget

TASK_STATUSES = ["Draft", "Planned", "In Progress", "Completed", "Cancelled"]
PRIORITIES = ["", "Low", "Medium", "High", "Critical"]

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
        apply_statusboard_table_behavior(self.table, stretch_last_section=True)
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


class QuickAssignmentsPanel(QWidget):
    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.incident_id = None if incident_id is None else str(incident_id)
        self._records: list[PlannedRecord] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        title = QLabel("Quick Assignments")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.status_label)
        layout.addLayout(header)

        fast_row = QHBoxLayout()
        self.assignment_edit = QLineEdit()
        self.assignment_edit.setPlaceholderText("Quick assignment")
        self.assignee_edit = QLineEdit()
        self.assignee_edit.setPlaceholderText("Assignee")
        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("Location / zone")
        self.due_edit = QLineEdit()
        self.due_edit.setPlaceholderText("Due")
        add_btn = QPushButton("Add")
        refresh_btn = QPushButton("Refresh")
        add_btn.clicked.connect(self.add_assignment)
        refresh_btn.clicked.connect(self.refresh)
        fast_row.addWidget(self.assignment_edit, 3)
        fast_row.addWidget(self.assignee_edit, 1)
        fast_row.addWidget(self.location_edit, 1)
        fast_row.addWidget(self.due_edit, 1)
        fast_row.addWidget(add_btn)
        fast_row.addWidget(refresh_btn)
        layout.addLayout(fast_row)

        options_row = QHBoxLayout()
        self.status_combo = QComboBox()
        self.status_combo.addItems(TASK_STATUSES)
        self.status_combo.setCurrentText("Planned")
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(PRIORITIES)
        self.priority_combo.setCurrentText("Medium")
        self.scheduled_edit = QLineEdit()
        self.scheduled_edit.setPlaceholderText("Scheduled")
        self.recurring_check = QCheckBox("Recurring?")
        self.recurrence_edit = QLineEdit()
        self.recurrence_edit.setPlaceholderText("Recurrence rule")
        self.recurrence_edit.setVisible(False)
        self.recurring_check.toggled.connect(self.recurrence_edit.setVisible)
        options_row.addWidget(QLabel("Status"))
        options_row.addWidget(self.status_combo)
        options_row.addWidget(QLabel("Priority"))
        options_row.addWidget(self.priority_combo)
        options_row.addWidget(self.scheduled_edit)
        options_row.addWidget(self.recurring_check)
        options_row.addWidget(self.recurrence_edit, 2)
        options_row.addStretch(1)
        layout.addLayout(options_row)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Notes")
        self.notes_edit.setFixedHeight(58)
        layout.addWidget(self.notes_edit)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels([
            "ID",
            "Assignment",
            "Status",
            "Priority",
            "Assignee",
            "Location / Zone",
            "Scheduled",
            "Due",
            "Source",
            "Action",
        ])
        apply_statusboard_table_behavior(self.table, stretch_last_section=True)
        layout.addWidget(self.table)

    def _iid(self) -> str | None:
        return self.incident_id

    def _set_status(self, message: str, *, error: bool = False) -> None:
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {'#b00020' if error else '#375a2b'};")

    def _describe_error(self, exc: Exception) -> str:
        if isinstance(exc, APIError):
            if exc.status_code is None:
                return f"Quick Assignments API unavailable: {exc}"
            return f"Quick Assignments API error {exc.status_code}: {exc}"
        return str(exc)

    def refresh(self) -> None:
        if not self._iid():
            self._records = []
            self.table.setRowCount(0)
            self._set_status("Select an incident to use this panel.", error=True)
            return
        try:
            rows = services.list_records("quick-assignments", self._iid())
        except Exception as exc:
            self._records = []
            self.table.setRowCount(0)
            self._set_status(self._describe_error(exc), error=True)
            return
        self._records = list(rows)
        self._populate()
        self._set_status(f"{len(self._records)} quick assignments")

    def add_assignment(self) -> None:
        if not self._iid():
            self._set_status("Select an incident before creating assignments.", error=True)
            return
        recurring = self.recurring_check.isChecked()
        try:
            services.create_record(
                "quick-assignments",
                self._iid(),
                title=self.assignment_edit.text().strip(),
                summary=self.notes_edit.toPlainText().strip(),
                status=self.status_combo.currentText().strip(),
                priority=self.priority_combo.currentText().strip(),
                assigned_to=self.assignee_edit.text().strip(),
                location=self.location_edit.text().strip(),
                zone=self.location_edit.text().strip(),
                scheduled_at=self.scheduled_edit.text().strip(),
                due_at=self.due_edit.text().strip(),
                recurring=recurring,
                recurrence_rule=self.recurrence_edit.text().strip() if recurring else "",
                missed_occurrence_behavior="latest_overdue" if recurring else "",
                lifecycle_state="Pending" if self.scheduled_edit.text().strip() else "Active",
            )
        except Exception as exc:
            self._set_status(self._describe_error(exc), error=True)
            return
        self.assignment_edit.clear()
        self.notes_edit.clear()
        self.assignee_edit.clear()
        self.location_edit.clear()
        self.scheduled_edit.clear()
        self.due_edit.clear()
        self.recurring_check.setChecked(False)
        self.recurrence_edit.clear()
        self.refresh()

    def _make_status_combo(self, record: PlannedRecord) -> QComboBox:
        combo = QComboBox()
        combo.addItems(TASK_STATUSES)
        if record.status in TASK_STATUSES:
            combo.setCurrentText(record.status)
        combo.setEnabled(not record.promoted_read_only)
        combo.currentTextChanged.connect(lambda value, rec_id=record.id: self._change_status(rec_id, value))
        return combo

    def _change_status(self, record_id: int | None, status: str) -> None:
        if not self._iid() or not record_id:
            return
        try:
            services.update_record("quick-assignments", int(record_id), {"status": status}, self._iid())
        except Exception as exc:
            self._set_status(self._describe_error(exc), error=True)
            self.refresh()
            return
        self._set_status("Status updated")

    def _make_action_button(self, record: PlannedRecord) -> QPushButton:
        if record.linked_tasking_id:
            button = QPushButton(f"Open Task {record.linked_tasking_id}")
            button.clicked.connect(lambda _=False, task_id=record.linked_tasking_id: self._open_tasking(task_id))
            return button
        button = QPushButton("Promote")
        button.clicked.connect(lambda _=False, rec_id=record.id: self._promote(rec_id))
        return button

    def _promote(self, record_id: int | None) -> None:
        if not self._iid() or not record_id:
            return
        try:
            promoted = services.promote_quick_assignment(int(record_id), self._iid())
        except Exception as exc:
            self._set_status(self._describe_error(exc), error=True)
            return
        self._set_status(f"Promoted to tasking {promoted.linked_tasking_id}")
        self.refresh()

    def _open_tasking(self, task_id: str) -> None:
        try:
            from modules.operations.taskings.windows import open_task_detail_window

            open_task_detail_window(int(task_id))
        except Exception as exc:
            self._set_status(f"Could not open full tasking: {exc}", error=True)

    def _source_text(self, record: PlannedRecord) -> str:
        if record.source_label:
            return record.source_label
        if record.source_type:
            return record.source_type
        if record.recurring:
            return "Recurring"
        return ""

    def _populate(self) -> None:
        self.table.setRowCount(len(self._records))
        for row_idx, record in enumerate(self._records):
            values = [
                str(record.id or ""),
                record.title,
                "",
                record.priority,
                record.assigned_to,
                record.zone or record.location,
                record.scheduled_at,
                record.due_at,
                self._source_text(record),
            ]
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem("" if value is None else str(value))
                if record.promoted_read_only:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    item.setToolTip(f"Promoted to full tasking {record.linked_tasking_id}")
                if col_idx == 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row_idx, col_idx, item)
            self.table.setCellWidget(row_idx, 2, self._make_status_combo(record))
            self.table.setCellWidget(row_idx, 9, self._make_action_button(record))


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
        tabs.addTab(QuickAssignmentsPanel(incident_id), "Quick Assignments")
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
    return QuickAssignmentsPanel(incident_id)


def get_health_sanitation_panel(incident_id: object | None = None) -> QWidget:
    return _ToolPanel(HEALTH_SPEC, incident_id)


def get_planned_toolkit_panel(incident_id: object | None = None) -> QWidget:
    return PlannedToolkitHome(incident_id)
