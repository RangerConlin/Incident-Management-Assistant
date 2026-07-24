"""
WorkAssignmentDetailWindow
==========================
Modeless window for viewing and editing one Work Assignment.

Tabs:
  1. Overview          — description, tactics summary, notes, metadata
  2. Resources/215     — resource requirements and actual assignments
  3. Hazards/215A      — hazard analysis entries
  4. Tasks             — linked Operations tasks
  5. Agency Requests    — linked ICS 213RR requests
  6. Outputs           — ICS 215 / 215A / 204 readiness tracking
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from modules.logistics.facilities.widgets import FacilityPicker
from modules.planning.tactics_resources.data.work_assignment_repository import WorkAssignmentRepository
from modules.planning.tactics_resources.models.work_assignment_models import (
    ASSIGNMENT_KIND_VALUES,
    OUTPUT_TYPE_VALUES,
    PLANNING_STATUS_VALUES,
    PRIORITY_VALUES,
    RESOURCE_STATUS_VALUES,
    SAFETY_STATUS_VALUES,
    WorkAssignment,
)
from modules.planning.tactics_resources.services.output_export_service import (
    generate_work_assignment_output,
)
from modules.planning.tactics_resources.widgets.hazard_analysis_editor import HazardAnalysisEditor
from modules.planning.tactics_resources.widgets.linked_agency_requests_panel import LinkedAgencyRequestsPanel
from modules.planning.tactics_resources.widgets.linked_tasks_panel import LinkedTasksPanel
from modules.planning.tactics_resources.widgets.resource_requirement_editor import ResourceRequirementEditor
from utils.styles import (
    get_palette,
    resource_status_colors,
    subscribe_theme,
    wa_planning_status_colors,
    wa_safety_status_colors,
)


def _format_display_timestamp(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    normalized = text.replace("T", " ")
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        if "." in normalized:
            normalized = normalized.split(".", 1)[0]
        return normalized[:19]
    return f"{dt:%b} {dt.day}, {dt.year} {dt:%H:%M:%S}"


def _format_op_time_range(start_time: object, end_time: object) -> str:
    start = _format_display_timestamp(start_time)
    end = _format_display_timestamp(end_time)
    if start and end:
        return f"{start} - {end}"
    return start or end


class WorkAssignmentDetailWindow(QWidget):
    """
    Modeless editing window for a single Work Assignment.

    Signals:
        saved(int) — emitted after a successful save with the work_assignment_id.
    """

    saved = Signal(int)

    def __init__(
        self,
        work_assignment_id: int | None = None,
        db_path: str | None = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setMinimumSize(900, 680)
        self._work_assignment_id = work_assignment_id
        self._db_path = db_path
        self._description_text = ""
        self._notes_text = ""
        self._prepared_by = ""
        self._approved_by = ""

        # Debounce timer — fires 800 ms after the last field change
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(800)
        self._save_timer.timeout.connect(self._auto_save)

        self._build_ui()
        self._update_title()
        self._refresh_status_chips()

        if work_assignment_id is not None:
            self._load()

        try:
            subscribe_theme(self, self._on_theme_changed)
        except Exception:
            pass

    def _on_theme_changed(self, _name: str) -> None:
        self._refresh_status_chips()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Top header bar
        self._header_box = self._build_header()
        layout.addWidget(self._header_box)

        # Tab widget
        self._tabs = QTabWidget(self)
        self._build_overview_tab()
        self._build_resources_tab()
        self._build_hazards_tab()
        self._build_tasks_tab()
        self._build_agency_requests_tab()
        self._build_outputs_tab()
        layout.addWidget(self._tabs, 1)

    def _build_header(self) -> QFrame:
        box = QFrame(self)
        box.setFrameShape(QFrame.StyledPanel)
        box.setAttribute(Qt.WA_StyledBackground, True)
        box.setStyleSheet(
            "QFrame { "
            f"background:{get_palette().get('bg_raised').name()}; "
            f"border:1px solid {get_palette().get('ctrl_border').name()}; "
            "border-radius:6px; "
            "}"
        )
        outer = QVBoxLayout(box)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        self._header_number_label = QLabel("New Strategy")
        self._header_number_label.setStyleSheet(
            f"color:{get_palette().get('accent').name()}; font-weight:700;"
        )
        self._header_op_label = QLabel("")
        self._header_op_label.setStyleSheet(
            f"color:{get_palette().get('accent').name()}; font-weight:700;"
        )
        top_row.addWidget(self._header_number_label)
        top_row.addWidget(self._header_op_label)
        top_row.addStretch(1)

        self._planning_chip = QLabel("")
        self._safety_chip = QLabel("")
        self._resource_chip = QLabel("")
        for chip in (self._planning_chip, self._safety_chip, self._resource_chip):
            top_row.addWidget(chip)
        outer.addLayout(top_row)

        self._header_title_label = QLabel("New Strategy")
        self._header_title_label.setStyleSheet("font-size:18px; font-weight:700;")
        outer.addWidget(self._header_title_label)

        self._header_meta_label = QLabel("")
        self._header_meta_label.setStyleSheet(
            f"color:{get_palette().get('fg_muted').name()};"
        )
        outer.addWidget(self._header_meta_label)

        self._summary_label = QLabel("Resources: - | Gap: - | Hazards: - | Unresolved: - | Tasks: -")
        self._summary_label.setStyleSheet(
            f"color:{get_palette().get('fg_muted').name()}; margin-top:4px;"
        )
        outer.addWidget(self._summary_label)

        return box

    @staticmethod
    def _style_chip(label: QLabel, text: str, brushes: dict | None) -> None:
        label.setText(text)
        if not brushes:
            label.setStyleSheet("")
            return
        bg = brushes["bg"].color().name()
        fg = brushes["fg"].color().name()
        label.setStyleSheet(
            f"background:{bg}; color:{fg}; padding:2px 8px; border-radius:4px; font-weight:700;"
        )

    def _refresh_status_chips(self) -> None:
        planning = (
            self._planning_status_combo.currentText()
            if hasattr(self, "_planning_status_combo")
            else "Draft"
        )
        safety = (
            self._safety_status_combo.currentText()
            if hasattr(self, "_safety_status_combo")
            else "Unchecked"
        )
        resource = (
            self._resource_status_combo.currentText()
            if hasattr(self, "_resource_status_combo")
            else "Unreviewed"
        )
        self._style_chip(self._planning_chip, planning, wa_planning_status_colors().get(planning))
        self._style_chip(self._safety_chip, safety, wa_safety_status_colors().get(safety))
        self._style_chip(self._resource_chip, resource, resource_status_colors().get(resource))
        self._refresh_header()

    def _refresh_header(self) -> None:
        if not hasattr(self, "_header_title_label") or not hasattr(self, "_name_edit"):
            return
        number = self._number_label.text().strip()
        name = self._name_edit.text().strip()
        self._header_number_label.setText(number or "New Strategy")
        op_text = self._op_period_combo.currentText().strip() if hasattr(self, "_op_period_combo") else ""
        op_text = op_text.split(" (", 1)[0]
        self._header_op_label.setText(f"OP: {op_text}" if op_text and op_text != "(none)" else "")
        self._header_title_label.setText(name or "New Strategy")

        meta_parts: list[str] = []
        branch = self._branch_combo.currentText().strip()
        division = self._division_combo.currentText().strip()
        if branch and branch != "(none)" and division and division != "(none)":
            meta_parts.append(f"{branch} / {division}")
        elif branch and branch != "(none)":
            meta_parts.append(branch)
        elif division and division != "(none)":
            meta_parts.append(division)
        location = self._location_picker.facility_text.strip()
        if location:
            meta_parts.append(location)
        prepared = self._prepared_by.strip()
        approved = self._approved_by.strip()
        if prepared:
            meta_parts.append(f"Prepared by {prepared}")
        if approved:
            meta_parts.append(f"Approved by {approved}")
        self._header_meta_label.setText(" | ".join(meta_parts))

    def _build_overview_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        assignment_title = QLabel("ASSIGNMENT")
        assignment_title.setStyleSheet(
            f"color:{get_palette().get('fg_muted').name()}; font-weight:700;"
        )
        layout.addWidget(assignment_title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Strategy name (required)")
        self._number_label = QLineEdit()
        self._number_label.setPlaceholderText("Strategy #")

        self._objective_combo = QComboBox()
        self._objective_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self._load_objectives()

        self._op_period_combo = QComboBox()
        self._op_period_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self._load_op_periods()

        self._branch_combo = QComboBox()
        self._branch_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self._load_branches()

        self._division_combo = QComboBox()
        self._division_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self._location_picker = FacilityPicker(facility_type=None, parent=self)
        self._location_picker.line_edit.setPlaceholderText("Reporting / destination location (optional)")

        self._kind_combo = QComboBox()
        self._kind_combo.addItems(ASSIGNMENT_KIND_VALUES)
        self._priority_combo = QComboBox()
        self._priority_combo.addItems(PRIORITY_VALUES)

        def _add_field(row: int, col: int, label: str, widget: QWidget, col_span: int = 1) -> None:
            lbl = QLabel(label.upper())
            lbl.setStyleSheet(
                f"color:{get_palette().get('fg_muted').name()}; font-size:11px; font-weight:700;"
            )
            grid.addWidget(lbl, row * 2, col)
            grid.addWidget(widget, row * 2 + 1, col, 1, col_span)

        _add_field(0, 0, "Assignment Name", self._name_edit, 2)
        _add_field(0, 2, "Assignment #", self._number_label)
        _add_field(1, 0, "Objective", self._objective_combo)
        _add_field(1, 1, "Branch", self._branch_combo)
        _add_field(1, 2, "Division / Group", self._division_combo)
        _add_field(2, 0, "Kind", self._kind_combo)
        _add_field(2, 1, "Priority", self._priority_combo)
        _add_field(3, 0, "Location / Facility", self._location_picker, 3)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        layout.addLayout(grid)

        self._planning_status_combo = QComboBox()
        self._planning_status_combo.addItems(PLANNING_STATUS_VALUES)
        self._resource_status_combo = QComboBox()
        self._resource_status_combo.addItems(RESOURCE_STATUS_VALUES)
        self._safety_status_combo = QComboBox()
        self._safety_status_combo.addItems(SAFETY_STATUS_VALUES)

        narrative_title = QLabel("OVERVIEW")
        narrative_title.setStyleSheet(
            f"color:{get_palette().get('fg_muted').name()}; font-weight:700;"
        )
        layout.addWidget(narrative_title)

        narrative_layout = QVBoxLayout()
        narrative_layout.setSpacing(8)

        def _add_text_area(label: str, widget: QPlainTextEdit, placeholder: str, min_height: int) -> None:
            lbl = QLabel(label.upper())
            lbl.setStyleSheet(
                f"color:{get_palette().get('fg_muted').name()}; font-size:11px; font-weight:700;"
            )
            widget.setPlaceholderText(placeholder)
            widget.setMinimumHeight(min_height)
            narrative_layout.addWidget(lbl)
            narrative_layout.addWidget(widget)

        self._tactics_edit = QPlainTextEdit()
        _add_text_area("Tactics Summary", self._tactics_edit, "Tactics summary", 84)

        self._instructions_edit = QPlainTextEdit()
        _add_text_area("Special Instructions", self._instructions_edit, "Special instructions", 84)

        # Wire overview fields for auto-save
        self._branch_combo.currentIndexChanged.connect(self._on_branch_changed)
        self._number_label.textChanged.connect(self._schedule_save)
        self._number_label.textChanged.connect(self._refresh_header)
        self._name_edit.textChanged.connect(self._schedule_save)
        self._name_edit.textChanged.connect(self._refresh_header)
        self._objective_combo.currentIndexChanged.connect(self._schedule_save)
        self._op_period_combo.currentIndexChanged.connect(self._refresh_header)
        self._branch_combo.currentIndexChanged.connect(self._schedule_save)
        self._branch_combo.currentIndexChanged.connect(self._refresh_header)
        self._division_combo.currentIndexChanged.connect(self._schedule_save)
        self._division_combo.currentIndexChanged.connect(self._refresh_header)
        self._location_picker.facilitySelected.connect(lambda *_: self._schedule_save())
        self._location_picker.facilitySelected.connect(lambda *_: self._refresh_header())
        self._location_picker.textChanged.connect(lambda *_: self._schedule_save())
        self._location_picker.textChanged.connect(lambda *_: self._refresh_header())
        self._kind_combo.currentIndexChanged.connect(self._schedule_save)
        self._priority_combo.currentIndexChanged.connect(self._schedule_save)
        self._planning_status_combo.currentIndexChanged.connect(self._schedule_save)
        self._safety_status_combo.currentIndexChanged.connect(self._schedule_save)
        self._resource_status_combo.currentIndexChanged.connect(self._schedule_save)
        self._planning_status_combo.currentIndexChanged.connect(self._refresh_status_chips)
        self._planning_status_combo.currentIndexChanged.connect(self._refresh_header)
        self._safety_status_combo.currentIndexChanged.connect(self._refresh_status_chips)
        self._resource_status_combo.currentIndexChanged.connect(self._refresh_status_chips)
        self._tactics_edit.textChanged.connect(self._schedule_save)
        self._instructions_edit.textChanged.connect(self._schedule_save)

        layout.addLayout(narrative_layout)
        layout.addStretch(1)
        self._tabs.addTab(tab, "Overview")

    def _build_resources_tab(self) -> None:
        placeholder = QWidget()
        lbl = QLabel("Save the strategy first to add resource requirements.", placeholder)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"color: {get_palette().get('muted').name()}; font-style: italic;")
        lay = QVBoxLayout(placeholder)
        lay.addWidget(lbl)
        self._resources_placeholder = placeholder
        self._resources_tab_index = self._tabs.addTab(self._resources_placeholder, "Resources / ICS 215")

    def _build_hazards_tab(self) -> None:
        placeholder = QWidget()
        lbl = QLabel("Save the strategy first to add hazard analysis entries.", placeholder)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"color: {get_palette().get('muted').name()}; font-style: italic;")
        lay = QVBoxLayout(placeholder)
        lay.addWidget(lbl)
        self._hazards_placeholder = placeholder
        self._hazards_tab_index = self._tabs.addTab(self._hazards_placeholder, "Hazards / ICS 215A")

    def _build_tasks_tab(self) -> None:
        placeholder = QWidget()
        lbl = QLabel("Save the strategy first to link or create tasks.", placeholder)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"color: {get_palette().get('muted').name()}; font-style: italic;")
        lay = QVBoxLayout(placeholder)
        lay.addWidget(lbl)
        self._tasks_placeholder = placeholder
        self._tasks_tab_index = self._tabs.addTab(self._tasks_placeholder, "Tasks")

    def _build_agency_requests_tab(self) -> None:
        placeholder = QWidget()
        lbl = QLabel("Save the strategy first to link agency requests.", placeholder)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"color: {get_palette().get('muted').name()}; font-style: italic;")
        lay = QVBoxLayout(placeholder)
        lay.addWidget(lbl)
        self._agency_requests_placeholder = placeholder
        self._agency_requests_tab_index = self._tabs.addTab(self._agency_requests_placeholder, "Agency Requests")

    def _build_outputs_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        self._outputs_layout = QVBoxLayout()
        self._outputs_layout.setSpacing(10)
        layout.addLayout(self._outputs_layout)
        layout.addStretch(1)

        self._tabs.addTab(tab, "Outputs")

    # ------------------------------------------------------------------
    # Combo population helpers
    # ------------------------------------------------------------------

    def _incident_id(self) -> str | None:
        try:
            from utils import incident_context
            return str(incident_context.get_active_incident_id() or "")
        except Exception:
            return None

    def _client(self):
        from utils.api_client import api_client
        return api_client

    def _load_op_periods(self) -> None:
        self._op_period_combo.clear()
        self._op_period_combo.addItem("(none)", None)
        iid = self._incident_id()
        if not iid:
            return
        try:
            rows = self._client().get(f"/api/incidents/{iid}/planning/operational-periods") or []
        except Exception:
            rows = []
        for row in rows:
            op_id = row.get("id") or row.get("int_id")
            number = row.get("number") or ""
            start_time = row.get("start_time") or ""
            end_time = row.get("end_time") or ""
            label = f"OP {number}"
            time_range = _format_op_time_range(start_time, end_time)
            if time_range:
                label += f" ({time_range})"
            self._op_period_combo.addItem(label, op_id)

    def _all_positions(self) -> list[dict]:
        iid = self._incident_id()
        if not iid:
            return []
        try:
            return self._client().get(f"/api/incidents/{iid}/org/positions") or []
        except Exception:
            return []

    def _load_objectives(self) -> None:
        self._objective_combo.clear()
        self._objective_combo.addItem("(none)", None)
        iid = self._incident_id()
        if not iid:
            return
        try:
            rows = self._client().get("/api/objectives", params={"incident_id": iid}) or []
        except Exception:
            rows = []
        for row in rows:
            code = row.get("code") or row.get("_id") or ""
            text = row.get("text") or ""
            label = f"{code} - {text}" if text else code
            self._objective_combo.addItem(label, row.get("_id"))

    def _load_branches(self) -> None:
        self._branch_combo.clear()
        self._branch_combo.addItem("(none)", None)
        for row in self._all_positions():
            if row.get("classification") == "branch" and row.get("status") == "active":
                self._branch_combo.addItem(row.get("title") or "", row.get("int_id") or row.get("id"))

    def _on_branch_changed(self) -> None:
        branch_pos_id = self._branch_combo.currentData()
        self._division_combo.clear()
        self._division_combo.addItem("(none)", None)
        if not branch_pos_id:
            return
        for row in self._all_positions():
            if (row.get("parent_position_id") == branch_pos_id
                    and row.get("status") == "active"
                    and row.get("classification") in ("division", "group")):
                classification = row.get("classification") or ""
                title = row.get("title") or ""
                label = f"{title} (Group)" if classification == "group" else title
                self._division_combo.addItem(label, row.get("int_id") or row.get("id"))

    # ------------------------------------------------------------------
    # Load / Save
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load work assignment data from DB and populate all tabs."""
        if self._work_assignment_id is None:
            return
        try:
            repo = WorkAssignmentRepository(self._db_path)
            wa = repo.get_work_assignment(self._work_assignment_id)
        except Exception as exc:
            QMessageBox.critical(self, "Load", f"Failed to load assignment:\n{exc}")
            return
        if not wa:
            QMessageBox.warning(self, "Load", "Work assignment not found.")
            return

        self._populate_header(wa)
        self._populate_overview(wa)
        self._populate_resource_tab()
        self._populate_hazard_tab()
        self._populate_tasks_tab()
        self._populate_agency_requests_tab()
        self._reload_outputs()
        self._update_summary()
        self._update_title()

    def _populate_header(self, wa: WorkAssignment) -> None:
        self._number_label.setText(wa.assignment_number)
        self._name_edit.setText(wa.assignment_name)
        self._load_objectives()
        obj_idx = self._objective_combo.findData(wa.objective_id)
        self._objective_combo.setCurrentIndex(obj_idx if obj_idx >= 0 else 0)

        # Reload combos from current DB state, then match stored values
        self._load_op_periods()
        op_idx = self._op_period_combo.findData(wa.operational_period_id)
        if op_idx >= 0:
            self._op_period_combo.setCurrentIndex(op_idx)

        self._load_branches()
        branch_idx = self._branch_combo.findText(wa.branch)
        if branch_idx >= 0:
            self._branch_combo.setCurrentIndex(branch_idx)
        # _on_branch_changed fires when branch index changes, populating divisions
        div_idx = self._division_combo.findText(wa.division_group)
        if div_idx >= 0:
            self._division_combo.setCurrentIndex(div_idx)
        self._location_picker.set_value(wa.location_facility_id, wa.location)

        kind_idx = self._kind_combo.findText(wa.assignment_kind)
        if kind_idx >= 0:
            self._kind_combo.setCurrentIndex(kind_idx)
        priority_idx = self._priority_combo.findText(wa.priority)
        if priority_idx >= 0:
            self._priority_combo.setCurrentIndex(priority_idx)

        idx = self._planning_status_combo.findText(wa.planning_status)
        if idx >= 0:
            self._planning_status_combo.setCurrentIndex(idx)
        idx = self._safety_status_combo.findText(wa.safety_status)
        if idx >= 0:
            self._safety_status_combo.setCurrentIndex(idx)
        idx = self._resource_status_combo.findText(wa.resource_status)
        if idx >= 0:
            self._resource_status_combo.setCurrentIndex(idx)
        self._refresh_status_chips()
        self._refresh_header()

    def _populate_overview(self, wa: WorkAssignment) -> None:
        self._description_text = wa.description
        self._notes_text = wa.notes
        self._prepared_by = str(wa.prepared_by or "")
        self._approved_by = str(wa.approved_by or "")
        self._tactics_edit.setPlainText(wa.tactics_summary)
        self._instructions_edit.setPlainText(wa.special_instructions)
        self._refresh_header()

    def _populate_resource_tab(self) -> None:
        """Replace the placeholder widget with a live ResourceRequirementEditor."""
        if self._work_assignment_id is None:
            return
        editor = ResourceRequirementEditor(
            self._work_assignment_id, db_path=self._db_path, parent=self
        )
        editor.changed.connect(self._update_summary)
        self._tabs.removeTab(self._resources_tab_index)
        self._tabs.insertTab(self._resources_tab_index, editor, "Resources / ICS 215")
        self._resources_placeholder = editor

    def _populate_hazard_tab(self) -> None:
        if self._work_assignment_id is None:
            return
        editor = HazardAnalysisEditor(
            self._work_assignment_id, db_path=self._db_path, parent=self
        )
        editor.changed.connect(self._update_summary)
        self._tabs.removeTab(self._hazards_tab_index)
        self._tabs.insertTab(self._hazards_tab_index, editor, "Hazards / ICS 215A")
        self._hazards_placeholder = editor

    def _populate_tasks_tab(self) -> None:
        if self._work_assignment_id is None:
            return
        panel = LinkedTasksPanel(
            self._work_assignment_id, db_path=self._db_path, parent=self
        )
        self._tabs.removeTab(self._tasks_tab_index)
        self._tabs.insertTab(self._tasks_tab_index, panel, "Tasks")
        self._tasks_placeholder = panel

    def _populate_agency_requests_tab(self) -> None:
        if self._work_assignment_id is None:
            return
        panel = LinkedAgencyRequestsPanel(
            self._work_assignment_id, db_path=self._db_path, parent=self
        )
        self._tabs.removeTab(self._agency_requests_tab_index)
        self._tabs.insertTab(self._agency_requests_tab_index, panel, "Agency Requests")
        self._agency_requests_placeholder = panel

    def _update_title(self) -> None:
        name = self._name_edit.text().strip() if hasattr(self, "_name_edit") else ""
        num = self._number_label.text() if hasattr(self, "_number_label") else ""
        if name:
            self.setWindowTitle(f"Strategy: {num} {name}".strip())
        else:
            self.setWindowTitle("Strategy: New")

    def _update_summary(self) -> None:
        """Refresh the counters in the header summary label."""
        if self._work_assignment_id is None:
            return
        try:
            repo = WorkAssignmentRepository(self._db_path)
            reqs = repo.list_resource_requirements(self._work_assignment_id)
            hazards = repo.list_hazards(self._work_assignment_id)
            links = repo.list_linked_tasks(self._work_assignment_id)
        except Exception:
            return
        total_req = sum(r.quantity_required for r in reqs)
        total_assigned = sum(r.quantity_assigned for r in reqs)
        total_gap = sum(max(r.quantity_required - r.quantity_assigned, 0) for r in reqs)
        unresolved = sum(1 for h in hazards if not h.is_resolved)
        self._summary_label.setText(
            f"Resources: {total_req} req / {total_assigned} assigned | "
            f"Gap: {total_gap} | "
            f"Hazards: {len(hazards)} ({unresolved} unresolved) | "
            f"Tasks: {len(links)}"
        )

    # ------------------------------------------------------------------
    # Save logic
    # ------------------------------------------------------------------

    def _collect_header_data(self) -> dict:
        """Collect all header form values into a data dict."""
        branch_text = self._branch_combo.currentText() if self._branch_combo.currentData() is not None else ""
        div_text = self._division_combo.currentText() if self._division_combo.currentData() is not None else ""
        return {
            "assignment_number": self._number_label.text().strip(),
            "assignment_name": self._name_edit.text().strip(),
            "objective_id": self._objective_combo.currentData(),
            "operational_period_id": self._op_period_combo.currentData(),
            "branch": branch_text,
            "division_group": div_text,
            "location": self._location_picker.facility_text,
            "location_facility_id": self._location_picker.facility_id,
            "assignment_kind": self._kind_combo.currentText(),
            "priority": self._priority_combo.currentText(),
            "planning_status": self._planning_status_combo.currentText(),
            "safety_status": self._safety_status_combo.currentText(),
            "resource_status": self._resource_status_combo.currentText(),
            "description": self._description_text,
            "tactics_summary": self._tactics_edit.toPlainText().strip(),
            "special_instructions": self._instructions_edit.toPlainText().strip(),
            "prepared_by": self._prepared_by or None,
            "approved_by": self._approved_by or None,
            "notes": self._notes_text,
        }

    def _schedule_save(self) -> None:
        """Restart the debounce timer; called whenever any field changes."""
        self._save_timer.start()

    def _auto_save(self) -> None:
        """Called by the debounce timer — save silently if a name is present."""
        data = self._collect_header_data()
        if not data.get("assignment_name"):
            return  # wait until the user types a name
        self._save(quiet=True)

    def _save(self, quiet: bool = False) -> bool:
        data = self._collect_header_data()
        if not data.get("assignment_name"):
            if not quiet:
                QMessageBox.warning(self, "Save", "Strategy name is required.")
            return False
        # Temporarily block field signals to prevent re-triggering auto-save
        self._save_timer.stop()
        try:
            repo = WorkAssignmentRepository(self._db_path)
            if self._work_assignment_id is None:
                new_id = repo.create_work_assignment(data)
                self._work_assignment_id = new_id
                self._populate_resource_tab()
                self._populate_hazard_tab()
                self._populate_tasks_tab()
                self._populate_agency_requests_tab()
                repo.add_log_entry(new_id, "Strategy created.", entry_type="System")
            else:
                repo.update_work_assignment(self._work_assignment_id, data)
                if not quiet:
                    repo.add_log_entry(self._work_assignment_id, "Strategy updated.", entry_type="System")
        except Exception as exc:
            if not quiet:
                QMessageBox.critical(self, "Save", f"Failed to save:\n{exc}")
            return False
        self._update_title()
        self._reload_outputs()
        self._refresh_header()
        self.saved.emit(self._work_assignment_id)
        return True

    # ------------------------------------------------------------------
    # Outputs tab
    # ------------------------------------------------------------------

    def _reload_outputs(self) -> None:
        if self._work_assignment_id is None:
            return
        try:
            repo = WorkAssignmentRepository(self._db_path)
            outputs = repo.list_outputs(self._work_assignment_id)
        except Exception:
            return
        while self._outputs_layout.count():
            item = self._outputs_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        by_type = {output.output_type: output for output in outputs}
        for output_type in OUTPUT_TYPE_VALUES:
            output = by_type.get(output_type)
            self._outputs_layout.addWidget(self._build_output_row(output_type, output))

    def _build_output_row(self, output_type: str, output) -> QFrame:
        row = QFrame(self)
        row.setFrameShape(QFrame.StyledPanel)
        row.setAttribute(Qt.WA_StyledBackground, True)
        row.setStyleSheet(
            "QFrame { "
            f"background:{get_palette().get('bg_raised').name()}; "
            f"border:1px solid {get_palette().get('ctrl_border').name()}; "
            "border-radius:6px; "
            "}"
        )
        layout = QHBoxLayout(row)
        layout.setContentsMargins(16, 12, 16, 12)
        title = QLabel(output_type)
        title.setStyleSheet("font-weight:700;")
        layout.addWidget(title, 1)

        generated_at = getattr(output, "generated_at", "") if output else ""
        generated_file_path = getattr(output, "generated_file_path", "") if output else ""
        status = getattr(output, "status", "Not Started") if output else "Not Started"
        notes = getattr(output, "notes", "") if output else ""
        has_file = bool(generated_file_path and Path(generated_file_path).exists())
        is_current = status in ("Ready", "Generated") and has_file
        if generated_at:
            meta = QLabel(f"Generated {_format_display_timestamp(generated_at)}")
        elif is_current:
            meta = QLabel(status)
        elif notes:
            meta = QLabel(notes)
        else:
            meta = QLabel("Not yet generated")
        meta.setStyleSheet(f"color:{get_palette().get('fg_muted').name()};")
        layout.addWidget(meta)

        badge_text = "Current" if is_current else status or "Not generated"
        badge = QLabel(badge_text)
        badge.setAlignment(Qt.AlignCenter)
        token = "success" if badge_text == "Current" else "warning" if badge_text not in ("Not Started", "Not generated") else "ctrl_border"
        badge.setStyleSheet(
            f"background:{get_palette().get(token).name()}; color:{get_palette().get('fg').name()}; "
            "padding:2px 8px; border-radius:4px; font-weight:700;"
        )
        layout.addWidget(badge)

        preview_btn = QPushButton("Preview")
        preview_btn.setEnabled(has_file)
        preview_btn.clicked.connect(
            lambda _checked=False, t=output_type, p=generated_file_path: self._preview_output_file(t, p)
        )
        layout.addWidget(preview_btn)
        generate_btn = QPushButton("Regenerate" if is_current or generated_at else "Generate")
        generate_btn.clicked.connect(lambda _checked=False, t=output_type: self._generate_output(t))
        layout.addWidget(generate_btn)
        return row

    def _generate_output(self, output_type: str) -> None:
        if self._work_assignment_id is None:
            if not self._save(quiet=False):
                return
        else:
            if not self._save(quiet=True):
                return
        try:
            result = generate_work_assignment_output(self._work_assignment_id, output_type)
            repo = WorkAssignmentRepository(self._db_path)
            repo.update_output_status(
                self._work_assignment_id,
                output_type,
                "Generated",
                generated_file_path=str(result.output_path),
                generated_at=result.generated_at,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Generate Output", f"Failed to generate {output_type}:\n{exc}")
            return
        self._reload_outputs()
        QMessageBox.information(self, "Generate Output", f"{output_type} generated:\n{result.output_path}")

    def _preview_output_file(self, output_type: str, generated_file_path: str) -> None:
        path = Path(generated_file_path or "")
        if not generated_file_path or not path.exists():
            QMessageBox.information(self, "Preview", f"Generate {output_type} before previewing it.")
            self._reload_outputs()
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        super().closeEvent(event)
