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

from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from modules.logistics.facilities.widgets import FacilityPicker
from modules.planning.tactics_resources.data.hazard_prefill_service import HazardPrefillService
from modules.planning.tactics_resources.data.resource_gap_service import ResourceGapService
from modules.planning.tactics_resources.data.work_assignment_repository import WorkAssignmentRepository
from modules.planning.tactics_resources.models.work_assignment_models import (
    OUTPUT_STATUS_VALUES,
    OUTPUT_TYPE_VALUES,
    PLANNING_STATUS_VALUES,
    RESOURCE_STATUS_VALUES,
    SAFETY_STATUS_VALUES,
    WorkAssignment,
)
from modules.planning.tactics_resources.widgets.hazard_analysis_editor import HazardAnalysisEditor
from modules.planning.tactics_resources.widgets.linked_agency_requests_panel import LinkedAgencyRequestsPanel
from modules.planning.tactics_resources.widgets.linked_tasks_panel import LinkedTasksPanel
from modules.planning.tactics_resources.widgets.resource_requirement_editor import ResourceRequirementEditor
from utils.table_view_styles import apply_statusboard_table_behavior
from utils.styles import (
    get_palette,
    resource_status_colors,
    subscribe_theme,
    wa_planning_status_colors,
    wa_safety_status_colors,
)


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
        self._gap_service = ResourceGapService(db_path)
        self._hazard_service = HazardPrefillService()

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

    def _build_header(self) -> QGroupBox:
        box = QGroupBox("Strategy")
        outer = QVBoxLayout(box)
        outer.setSpacing(4)

        # ---- Action button bar (top) ----
        btn_bar = QHBoxLayout()
        self._recalc_btn = QPushButton("Recalculate Gaps")
        self._apply_hazards_btn = QPushButton("Apply Default Hazards")
        self._create_task_btn = QPushButton("Create Operations Task")
        self._link_task_btn = QPushButton("Link Existing Task")
        for btn in (self._recalc_btn, self._apply_hazards_btn,
                    self._create_task_btn, self._link_task_btn):
            btn_bar.addWidget(btn)
        btn_bar.addStretch(1)
        outer.addLayout(btn_bar)

        # ---- Two-column field area ----
        cols = QHBoxLayout()
        cols.setSpacing(16)

        left_form = QFormLayout()
        left_form.setLabelAlignment(Qt.AlignRight)
        left_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        left_form.setSpacing(4)

        self._number_label = QLabel("")
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Strategy name (required)")
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

        self._branch_combo.currentIndexChanged.connect(self._on_branch_changed)

        left_form.addRow("Strategy #", self._number_label)
        left_form.addRow("Name *", self._name_edit)
        left_form.addRow("Objective", self._objective_combo)
        left_form.addRow("Oper. Period", self._op_period_combo)
        left_form.addRow("Branch", self._branch_combo)
        left_form.addRow("Division / Group", self._division_combo)
        left_form.addRow("Location", self._location_picker)

        right_form = QFormLayout()
        right_form.setLabelAlignment(Qt.AlignRight)
        right_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        right_form.setSpacing(4)

        self._planning_status_combo = QComboBox()
        self._planning_status_combo.addItems(PLANNING_STATUS_VALUES)
        self._safety_status_combo = QComboBox()
        self._safety_status_combo.addItems(SAFETY_STATUS_VALUES)
        self._resource_status_combo = QComboBox()
        self._resource_status_combo.addItems(RESOURCE_STATUS_VALUES)

        right_form.addRow("Planning Status", self._planning_status_combo)
        right_form.addRow("Safety Status", self._safety_status_combo)
        right_form.addRow("Resource Status", self._resource_status_combo)

        cols.addLayout(left_form, 3)
        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setFrameShadow(QFrame.Sunken)
        cols.addWidget(divider)
        cols.addLayout(right_form, 2)
        outer.addLayout(cols)

        # ---- Status chip row ----
        chip_row = QHBoxLayout()
        self._planning_chip = QLabel("")
        self._safety_chip = QLabel("")
        self._resource_chip = QLabel("")
        for chip in (self._planning_chip, self._safety_chip, self._resource_chip):
            chip_row.addWidget(chip)
        chip_row.addStretch(1)
        outer.addLayout(chip_row)

        # ---- Summary line ----
        self._summary_label = QLabel("Resources: — | Gap: — | Hazards: — | Unresolved: — | Tasks: —")
        outer.addWidget(self._summary_label)

        # ---- Wire action buttons ----
        self._recalc_btn.clicked.connect(self._recalculate)
        self._apply_hazards_btn.clicked.connect(self._apply_hazards)
        self._create_task_btn.clicked.connect(self._create_task)
        self._link_task_btn.clicked.connect(self._link_task)

        # ---- Wire auto-save on every field change ----
        self._name_edit.textChanged.connect(self._schedule_save)
        self._objective_combo.currentIndexChanged.connect(self._schedule_save)
        self._op_period_combo.currentIndexChanged.connect(self._schedule_save)
        self._branch_combo.currentIndexChanged.connect(self._schedule_save)
        self._division_combo.currentIndexChanged.connect(self._schedule_save)
        self._location_picker.facilitySelected.connect(lambda *_: self._schedule_save())
        self._location_picker.textChanged.connect(lambda *_: self._schedule_save())
        self._planning_status_combo.currentIndexChanged.connect(self._schedule_save)
        self._safety_status_combo.currentIndexChanged.connect(self._schedule_save)
        self._resource_status_combo.currentIndexChanged.connect(self._schedule_save)
        self._planning_status_combo.currentIndexChanged.connect(self._refresh_status_chips)
        self._safety_status_combo.currentIndexChanged.connect(self._refresh_status_chips)
        self._resource_status_combo.currentIndexChanged.connect(self._refresh_status_chips)

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
        planning = self._planning_status_combo.currentText()
        safety = self._safety_status_combo.currentText()
        resource = self._resource_status_combo.currentText()
        self._style_chip(self._planning_chip, planning, wa_planning_status_colors().get(planning))
        self._style_chip(self._safety_chip, safety, wa_safety_status_colors().get(safety))
        self._style_chip(self._resource_chip, resource, resource_status_colors().get(resource))

    def _build_overview_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        form = QFormLayout()
        self._description_edit = QPlainTextEdit()
        self._description_edit.setPlaceholderText("Assignment description")
        self._description_edit.setFixedHeight(80)
        form.addRow("Description", self._description_edit)

        self._tactics_edit = QPlainTextEdit()
        self._tactics_edit.setPlaceholderText("Tactics summary")
        self._tactics_edit.setFixedHeight(80)
        form.addRow("Tactics Summary", self._tactics_edit)

        self._instructions_edit = QPlainTextEdit()
        self._instructions_edit.setPlaceholderText("Special instructions")
        self._instructions_edit.setFixedHeight(60)
        form.addRow("Special Instructions", self._instructions_edit)

        self._notes_edit = QPlainTextEdit()
        self._notes_edit.setPlaceholderText("Notes")
        self._notes_edit.setFixedHeight(60)
        form.addRow("Notes", self._notes_edit)

        self._prepared_edit = QLineEdit()
        form.addRow("Prepared By", self._prepared_edit)

        self._approved_edit = QLineEdit()
        form.addRow("Approved By", self._approved_edit)

        self._meta_label = QLabel("")
        self._meta_label.setStyleSheet(f"color: {get_palette().get('muted').name()}; font-size: 11px;")
        form.addRow("Created / Updated", self._meta_label)

        # Wire overview fields for auto-save
        self._description_edit.textChanged.connect(self._schedule_save)
        self._tactics_edit.textChanged.connect(self._schedule_save)
        self._instructions_edit.textChanged.connect(self._schedule_save)
        self._notes_edit.textChanged.connect(self._schedule_save)
        self._prepared_edit.textChanged.connect(self._schedule_save)
        self._approved_edit.textChanged.connect(self._schedule_save)

        layout.addLayout(form)
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

        btn_bar = QHBoxLayout()
        self._output_ready_btn = QPushButton("Mark Ready")
        self._output_review_btn = QPushButton("Mark Needs Review")
        self._output_preview_btn = QPushButton("Preview Data")
        for b in (self._output_ready_btn, self._output_review_btn, self._output_preview_btn):
            btn_bar.addWidget(b)
        btn_bar.addStretch(1)
        layout.addLayout(btn_bar)

        columns = ["Output Type", "Status", "Last Generated", "Generated By", "Notes"]
        self._outputs_table = QTableWidget(0, len(columns))
        self._outputs_table.setHorizontalHeaderLabels(columns)
        apply_statusboard_table_behavior(self._outputs_table, stretch_last_section=True)
        layout.addWidget(self._outputs_table)

        self._output_ready_btn.clicked.connect(lambda: self._set_output_status("Ready"))
        self._output_review_btn.clicked.connect(lambda: self._set_output_status("Needs Review"))
        self._output_preview_btn.clicked.connect(self._preview_output_data)

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
            if start_time:
                label += f" ({start_time}"
                if end_time:
                    label += f" – {end_time}"
                label += ")"
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

    def _populate_overview(self, wa: WorkAssignment) -> None:
        self._description_edit.setPlainText(wa.description)
        self._tactics_edit.setPlainText(wa.tactics_summary)
        self._instructions_edit.setPlainText(wa.special_instructions)
        self._notes_edit.setPlainText(wa.notes)
        self._prepared_edit.setText(str(wa.prepared_by or ""))
        self._approved_edit.setText(str(wa.approved_by or ""))
        self._meta_label.setText(f"Created: {wa.created_at}   Updated: {wa.updated_at}")

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
            "assignment_name": self._name_edit.text().strip(),
            "objective_id": self._objective_combo.currentData(),
            "operational_period_id": self._op_period_combo.currentData(),
            "branch": branch_text,
            "division_group": div_text,
            "location": self._location_picker.facility_text,
            "location_facility_id": self._location_picker.facility_id,
            "planning_status": self._planning_status_combo.currentText(),
            "safety_status": self._safety_status_combo.currentText(),
            "resource_status": self._resource_status_combo.currentText(),
            "description": self._description_edit.toPlainText().strip(),
            "tactics_summary": self._tactics_edit.toPlainText().strip(),
            "special_instructions": self._instructions_edit.toPlainText().strip(),
            "notes": self._notes_edit.toPlainText().strip(),
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
        self.saved.emit(self._work_assignment_id)
        return True

    # ------------------------------------------------------------------
    # Header action buttons
    # ------------------------------------------------------------------

    def _recalculate(self) -> None:
        if self._work_assignment_id is None:
            QMessageBox.information(self, "Recalculate", "Save the assignment first.")
            return
        try:
            repo = WorkAssignmentRepository(self._db_path)
            repo.recalculate_all_resource_gaps(self._work_assignment_id)
        except Exception as exc:
            QMessageBox.critical(self, "Recalculate", f"Failed:\n{exc}")
            return
        # Reload the resource tab if it's a live editor
        if isinstance(self._resources_placeholder, ResourceRequirementEditor):
            self._resources_placeholder.reload()
        self._update_summary()

    def _apply_hazards(self) -> None:
        if self._work_assignment_id is None:
            QMessageBox.information(self, "Apply Hazards", "Save the assignment first.")
            return
        try:
            added, skipped = self._hazard_service.apply_default_hazards(self._work_assignment_id)
        except Exception as exc:
            QMessageBox.critical(self, "Apply Hazards", f"Failed:\n{exc}")
            return
        if isinstance(self._hazards_placeholder, HazardAnalysisEditor):
            self._hazards_placeholder.reload()
        self._update_summary()
        if added == 0 and skipped == 0:
            QMessageBox.information(
                self, "Default Hazards",
                "No default hazards are configured for this strategy's resource types.\n\n"
                "Default hazards are assigned per resource type in the Hazard Type Library "
                "(Admin > Hazard Types > open a hazard type > 'Resource Type Defaults' tab).",
            )
        else:
            QMessageBox.information(
                self, "Default Hazards",
                f"Added {added} hazard(s). Skipped {skipped} (already present or unavailable).",
            )

    def _create_task(self) -> None:
        if self._work_assignment_id is None:
            QMessageBox.information(self, "Create Task", "Save the assignment first.")
            return
        if isinstance(self._tasks_placeholder, LinkedTasksPanel):
            self._tasks_placeholder._create_task()
            self._update_summary()

    def _link_task(self) -> None:
        if self._work_assignment_id is None:
            QMessageBox.information(self, "Link Task", "Save the assignment first.")
            return
        if isinstance(self._tasks_placeholder, LinkedTasksPanel):
            self._tasks_placeholder._link_existing()
            self._update_summary()

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
        self._outputs_table.setRowCount(0)
        for o in outputs:
            row = self._outputs_table.rowCount()
            self._outputs_table.insertRow(row)
            self._outputs_table.setItem(row, 0, QTableWidgetItem(o.output_type))
            self._outputs_table.setItem(row, 1, QTableWidgetItem(o.status))
            self._outputs_table.setItem(row, 2, QTableWidgetItem(o.generated_at))
            self._outputs_table.setItem(row, 3, QTableWidgetItem(str(o.generated_by or "")))
            self._outputs_table.setItem(row, 4, QTableWidgetItem(o.notes))
            self._outputs_table.item(row, 0).setData(Qt.UserRole, o.output_type)

    def _set_output_status(self, status: str) -> None:
        row = self._outputs_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Output Status", "Select an output row first.")
            return
        output_type = self._outputs_table.item(row, 0).data(Qt.UserRole)
        try:
            repo = WorkAssignmentRepository(self._db_path)
            repo.update_output_status(self._work_assignment_id, output_type, status)
        except Exception as exc:
            QMessageBox.critical(self, "Output Status", f"Failed:\n{exc}")
            return
        self._reload_outputs()

    def _preview_output_data(self) -> None:
        """Show a plain-text preview of all assignment data."""
        if self._work_assignment_id is None:
            return
        summary = self._gap_service.summarize_assignment_resources(self._work_assignment_id)
        try:
            repo = WorkAssignmentRepository(self._db_path)
            wa = repo.get_work_assignment(self._work_assignment_id)
            hazards = repo.list_hazards(self._work_assignment_id)
            links = repo.list_linked_tasks(self._work_assignment_id)
        except Exception as exc:
            QMessageBox.critical(self, "Preview", f"Failed:\n{exc}")
            return
        lines = [
            f"Strategy: {wa.assignment_number} {wa.assignment_name}",
            f"Kind: {wa.assignment_kind}  Priority: {wa.priority}  Status: {wa.planning_status}",
            f"Branch: {wa.branch}  Division/Group: {wa.division_group}",
            "",
            "--- Description ---",
            wa.description or "(none)",
            "",
            "--- Tactics Summary ---",
            wa.tactics_summary or "(none)",
            "",
            "--- Resources ---",
            summary,
            "",
            "--- Hazards ---",
        ]
        for h in hazards:
            lines.append(
                f"  • {h.hazard_type_text}  Risk:{h.risk_level}  Resolved:{'Yes' if h.is_resolved else 'No'}"
            )
        lines += ["", "--- Linked Tasks ---"]
        for lnk in links:
            lines.append(f"  Task {lnk.task_id} ({lnk.link_type})")

        preview_text = "\n".join(lines)
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QPlainTextEdit, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle("Output Data Preview")
        dlg.setMinimumSize(600, 500)
        lay = QVBoxLayout(dlg)
        text_edit = QPlainTextEdit()
        text_edit.setPlainText(preview_text)
        text_edit.setReadOnly(True)
        lay.addWidget(text_edit)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        dlg.exec()

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        super().closeEvent(event)
