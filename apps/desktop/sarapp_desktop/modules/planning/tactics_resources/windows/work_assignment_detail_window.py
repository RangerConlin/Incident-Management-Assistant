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
  6. Outputs           — ICS 215 / 215A / 213RR readiness tracking
  7. Approvals         — Safety/OSC/PSC/LSC sign-off chain
"""
from __future__ import annotations

import logging
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
    QInputDialog,
    QLabel,
    QLineEdit,
    QLayout,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from modules.approvals.models import ApprovalInstance, StepInstance
from modules.approvals.service import ApprovalService
from modules.logistics.facilities.widgets import FacilityPicker
from modules.planning.tactics_resources.data.work_assignment_desk import (
    resolve_person_name,
    work_assignment_desk,
)
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
from utils.state import AppState
from utils.styles import (
    approval_step_status_colors,
    get_palette,
    wa_resource_status_colors,
    subscribe_theme,
    wa_planning_status_colors,
    wa_priority_colors,
    wa_safety_status_colors,
)

logger = logging.getLogger(__name__)

# Work assignment approval chain — step_id must match the spec registered
# server-side under entity_type "work_assignment"
# (server/sarapp_db/sarapp_db/api/routers/approvals.py). Safety Officer is
# the only real approve/reject gate; the other three just acknowledge
# ("Reviewed").
_WA_APPROVAL_STEPS: list[tuple[str, str, str, bool]] = [
    ("sofr_approval", "Safety Officer", "SOFR", True),
    ("osc_review", "Operations Section Chief", "OSC", False),
    ("psc_review", "Planning Section Chief", "PSC", False),
    ("lsc_review", "Logistics Section Chief", "LSC", False),
]


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
        self._work_assignment_id = work_assignment_id
        self._db_path = db_path
        self._description_text = ""
        self._notes_text = ""
        self._prepared_by = ""
        self._approved_by = ""
        self._updated_at = ""
        self._updated_by = ""
        self._save_state = "Saved"

        # Debounce timer — fires 800 ms after the last field change
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(800)
        self._save_timer.timeout.connect(self._auto_save)

        self._build_ui()
        self.resize(960, 860)
        self._apply_window_stylesheet()
        self._update_title()
        self._refresh_status_chips()
        self._update_summary()
        self._reload_approvals()

        if work_assignment_id is not None:
            self._load()

        try:
            subscribe_theme(self, self._on_theme_changed)
        except Exception:
            pass

    def _apply_window_stylesheet(self) -> None:
        """Bold flat field styling matching the approved mockup — larger
        radius, generous padding, accent-colored focus state, borderless
        combo drop-downs. The app's own shared stylesheet
        (`styles/qss_helpers.global_qss`) already reaches this window but
        is deliberately subtle (1px borders, 3px radius, 2px padding) and
        was never meant to look like this redesign, so this window defines
        its own rules instead of reusing that one. Scoped automatically to
        this window's own widget subtree (a stylesheet set directly on a
        widget never leaks outside it), so nothing else in the app is
        affected."""
        p = get_palette()
        bg_field = p.get("ctrl_bg").name()
        bg_field_hover = p.get("ctrl_hover").name()
        border = p.get("ctrl_border").name()
        accent = p.get("ctrl_focus").name()
        text = p.get("fg_primary").name()
        muted = p.get("fg_muted").name()
        bg_raised = p.get("bg_raised").name()
        btn_bg = p.get("btn_bg").name()
        btn_border = p.get("btn_border").name()
        btn_hover = p.get("btn_hover").name()
        divider = p.get("divider").name()
        panel_bg = p.get("bg_panel").name()
        primary_fg = p.get("btn_primary_fg").name()
        danger = p.get("danger").name()
        success = p.get("success").name()
        self.setStyleSheet(f"""
            WorkAssignmentDetailWindow {{
                background: {panel_bg};
            }}
            QFrame#workAssignmentHeader, QFrame#workAssignmentFooter {{
                background: {panel_bg};
                border: none;
            }}
            QFrame#workAssignmentStatStrip {{
                background: {divider};
                border: none;
                border-radius: 0px;
            }}
            QScrollArea#workAssignmentOverviewScroll,
            QWidget#workAssignmentOverviewContent {{
                background: {panel_bg};
                border: none;
            }}
            QLineEdit, QPlainTextEdit, QComboBox {{
                background: {bg_field};
                color: {text};
                border: 1px solid {border};
                border-radius: 6px;
                padding: 8px 10px;
                font-size: 13px;
                selection-background-color: {accent};
            }}
            QLineEdit:hover, QPlainTextEdit:hover, QComboBox:hover {{
                background: {bg_field_hover};
            }}
            QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
                border: 1px solid {accent};
                background: {bg_field_hover};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 22px;
                border: none;
                background: transparent;
            }}
            QComboBox QAbstractItemView {{
                background: {bg_raised};
                color: {text};
                border: 1px solid {border};
                border-radius: 6px;
                selection-background-color: {bg_field_hover};
                selection-color: {text};
                padding: 4px;
            }}
            QPushButton {{
                background: {btn_bg};
                color: {text};
                border: 1px solid {btn_border};
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 12.5px;
            }}
            QPushButton:hover {{
                background: {btn_hover};
            }}
            QPushButton#workAssignmentPrimaryButton {{
                background: {accent};
                color: {primary_fg};
                border-color: {accent};
            }}
            QPushButton#workAssignmentPrimaryButton:hover {{
                background: {accent};
            }}
            QPushButton#workAssignmentDangerButton {{
                background: transparent;
                color: {danger};
                border-color: {danger};
            }}
            QPushButton:disabled {{
                color: {muted};
            }}
            QLabel#workAssignmentSaveState[saveState="saved"] {{ color: {success}; }}
            QLabel#workAssignmentSaveState[saveState="dirty"] {{ color: {muted}; }}
            QLabel#workAssignmentSaveState[saveState="saving"] {{ color: {accent}; }}
            QLabel#workAssignmentSaveState[saveState="error"] {{ color: {danger}; }}
            QTabWidget::pane {{
                border: none;
                border-top: 1px solid {divider};
                padding: 0px;
            }}
            QTabBar {{
                background: transparent;
            }}
            QTabBar::tab {{
                background: transparent;
                color: {muted};
                border: none;
                border-bottom: 2px solid transparent;
                padding: 10px 12px;
                margin-right: 0px;
                font-weight: 600;
                font-size: 12.5px;
            }}
            QTabBar::tab:selected {{
                color: {accent};
                border-bottom: 2px solid {accent};
            }}
            QTabBar::tab:hover {{
                color: {text};
            }}
            QTableView {{
                background: {panel_bg};
                alternate-background-color: {bg_field};
                border: 1px solid {border};
                border-radius: 6px;
                gridline-color: {divider};
            }}
            QHeaderView::section {{
                background: {panel_bg};
                color: {muted};
                border: none;
                border-bottom: 1px solid {border};
                padding: 7px 9px;
            }}
            QGroupBox {{
                border: none;
                margin-top: 18px;
                font-size: 11px;
                font-weight: 700;
                color: {muted};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 0px;
                padding: 0px;
            }}
        """)

    def _on_theme_changed(self, _name: str) -> None:
        self._apply_window_stylesheet()
        self._refresh_status_chips()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        # Deliberately allow the user to shrink the window below every child
        # widget's combined size hint. Qt otherwise derives an implicit
        # minimum from the wide tab labels and toolbar buttons.
        layout.setSizeConstraint(QLayout.SetNoConstraint)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top header bar
        self._header_box = self._build_header()
        layout.addWidget(self._header_box)

        # The quick-glance strip belongs to the assignment as a whole, not
        # only to Overview, so it remains visible while the user changes tabs.
        layout.addWidget(self._build_stat_row())

        # Tab widget
        self._tabs = QTabWidget(self)
        self._build_overview_tab()
        self._build_resources_tab()
        self._build_hazards_tab()
        self._build_tasks_tab()
        self._build_agency_requests_tab()
        self._build_outputs_tab()
        self._build_approvals_tab()
        layout.addWidget(self._tabs, 1)

        self._footer_box = self._build_footer()
        layout.addWidget(self._footer_box)

    def _build_header(self) -> QFrame:
        box = QFrame(self)
        box.setObjectName("workAssignmentHeader")
        box.setFrameShape(QFrame.NoFrame)
        box.setAttribute(Qt.WA_StyledBackground, True)
        outer = QVBoxLayout(box)
        outer.setContentsMargins(24, 18, 24, 16)
        outer.setSpacing(8)

        muted = get_palette().get("fg_muted").name()
        accent = get_palette().get("accent").name()

        eyebrow = QLabel("PLANNING  ·  WORK ASSIGNMENT")
        eyebrow.setStyleSheet(f"color:{muted}; font-size:10px; font-weight:700; letter-spacing:1px;")
        outer.addWidget(eyebrow)

        name_row = QHBoxLayout()
        name_row.setSpacing(12)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Name this assignment…")
        self._name_edit.setStyleSheet(
            "QLineEdit { border:none; background:transparent; font-size:19px; font-weight:700; "
            "padding:2px 0; border-bottom:2px solid transparent; }"
            f"QLineEdit:focus {{ border-bottom:2px solid {accent}; }}"
        )
        name_row.addWidget(self._name_edit, 1)

        self._planning_status_combo = QComboBox()
        self._planning_status_combo.addItems(PLANNING_STATUS_VALUES)
        self._planning_status_combo.setToolTip("Planning status")
        self._safety_status_combo = QComboBox()
        self._safety_status_combo.addItems(SAFETY_STATUS_VALUES)
        self._safety_status_combo.setToolTip("Safety status")
        self._resource_status_combo = QComboBox()
        self._resource_status_combo.addItems(RESOURCE_STATUS_VALUES)
        self._resource_status_combo.setToolTip("Resource status")

        for combo in (self._planning_status_combo, self._safety_status_combo, self._resource_status_combo):
            combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
            combo.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
            widest_text = max(
                (combo.fontMetrics().horizontalAdvance(combo.itemText(index)) for index in range(combo.count())),
                default=0,
            )
            combo.setFixedWidth(min(widest_text + 34, 190))
            name_row.addWidget(combo)
        outer.addLayout(name_row)

        self._header_number_label = QLabel("New Work Assignment")
        self._header_number_label.setStyleSheet(f"color:{muted}; font-size:11px;")
        self._header_op_label = QLabel("")
        self._header_op_label.setStyleSheet(f"color:{accent}; font-size:11px; font-weight:700;")

        self._header_meta_label = QLabel("")
        self._header_meta_label.setStyleSheet(f"color:{muted}; font-size:11px;")
        self._header_meta_label.setWordWrap(True)

        sub_row = QHBoxLayout()
        sub_row.setSpacing(10)
        sub_row.addWidget(self._header_number_label)
        sub_row.addWidget(self._header_op_label)
        sub_row.addWidget(self._header_meta_label, 1)
        outer.addLayout(sub_row)

        return box

    def _build_footer(self) -> QFrame:
        footer = QFrame(self)
        footer.setObjectName("workAssignmentFooter")
        footer.setFrameShape(QFrame.NoFrame)
        footer.setAttribute(Qt.WA_StyledBackground, True)
        footer.setStyleSheet(
            f"QFrame#workAssignmentFooter {{ border-top:1px solid {get_palette().get('divider').name()}; }}"
        )
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(10)

        self._save_state_label = QLabel("Saved")
        self._save_state_label.setObjectName("workAssignmentSaveState")
        self._save_state_label.setProperty("saveState", "saved")
        layout.addWidget(self._save_state_label)
        layout.addStretch(1)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("workAssignmentPrimaryButton")
        save_btn.clicked.connect(lambda _checked=False: self._save(quiet=False))
        layout.addWidget(save_btn)
        return footer

    def _build_stat_row(self) -> QFrame:
        """Quick-glance Priority/Resources/Gap/Hazards/Tasks strip, shown at
        the top of the Overview tab — one flush bar with hairline dividers
        between cells (matching the approved mockup), not separate floating
        cards."""
        bar = QFrame()
        bar.setObjectName("workAssignmentStatStrip")
        bar.setFrameShape(QFrame.NoFrame)
        bar.setAttribute(Qt.WA_StyledBackground, True)
        divider = get_palette().get("divider").name()
        bar.setStyleSheet(
            "QFrame#workAssignmentStatStrip { "
            f"background:{divider}; "
            "border:none; "
            "}"
        )
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(1)
        self._stat_cards: dict[str, tuple[QWidget, QLabel]] = {}
        panel_bg = get_palette().get("bg_panel").name()
        for key, title in (
            ("priority", "Priority"),
            ("resources", "Resources"),
            ("gap", "Gap"),
            ("hazards", "Open Hazards"),
            ("tasks", "Linked Tasks"),
        ):
            cell = QWidget()
            cell.setAttribute(Qt.WA_StyledBackground, True)
            cell.setStyleSheet(f"background:{panel_bg};")
            layout = QVBoxLayout(cell)
            layout.setContentsMargins(18, 12, 18, 12)
            layout.setSpacing(3)
            label = QLabel(title.upper())
            label.setStyleSheet(
                f"color:{get_palette().get('fg_muted').name()}; font-size:10px; font-weight:700; "
                "letter-spacing:0.5px; background:transparent;"
            )
            value = QLabel("-")
            value.setStyleSheet("font-size:16px; font-weight:700; background:transparent;")
            layout.addWidget(label)
            layout.addWidget(value)
            row.addWidget(cell, 1)
            self._stat_cards[key] = (cell, value)
        return bar

    @staticmethod
    def _style_status_combo(combo: QComboBox, brushes: dict | None) -> None:
        """Make a status QComboBox read as a colored pill, matching the
        read-only chip look it replaces, while staying a real editable control."""
        if not brushes:
            combo.setStyleSheet("")
            return
        bg = brushes["bg"].color().name()
        fg = brushes["fg"].color().name()
        popup_bg = get_palette().get("bg_raised").name()
        popup_fg = get_palette().get("fg").name()
        combo.setStyleSheet(
            "QComboBox { "
            f"background:{bg}; color:{fg}; padding:2px 8px; border-radius:4px; "
            "border:none; font-weight:700; }"
            "QComboBox::drop-down { border:none; width:16px; }"
            "QComboBox QAbstractItemView { "
            f"background:{popup_bg}; color:{popup_fg}; }}"
        )

    def _refresh_status_chips(self) -> None:
        self._style_status_combo(
            self._planning_status_combo,
            wa_planning_status_colors().get(self._planning_status_combo.currentText()),
        )
        self._style_status_combo(
            self._safety_status_combo,
            wa_safety_status_colors().get(self._safety_status_combo.currentText()),
        )
        self._style_status_combo(
            self._resource_status_combo,
            wa_resource_status_colors().get(self._resource_status_combo.currentText()),
        )
        self._refresh_header()

    def _refresh_header(self) -> None:
        if not hasattr(self, "_header_number_label") or not hasattr(self, "_name_edit"):
            return
        number = self._number_label.text().strip()
        self._header_number_label.setText(number or "Not yet saved")
        op_text = self._op_period_combo.currentText().strip() if hasattr(self, "_op_period_combo") else ""
        op_text = op_text.split(" (", 1)[0]
        self._header_op_label.setText(f"OP: {op_text}" if op_text and op_text != "(none)" else "")

        meta_parts: list[str] = []
        objective_text = self._objective_combo.currentText().strip() if hasattr(self, "_objective_combo") else ""
        if objective_text and objective_text != "(none)":
            meta_parts.append(objective_text)
        else:
            meta_parts.append("No objective linked")
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
            meta_parts.append(f"Prepared by {resolve_person_name(prepared)}")
        if approved:
            meta_parts.append(f"Approved by {resolve_person_name(approved)}")
        if self._updated_at:
            updated_text = f"Updated {_format_display_timestamp(self._updated_at)}"
            if self._updated_by:
                updated_text += f" by {resolve_person_name(self._updated_by)}"
            meta_parts.append(updated_text)
        self._header_meta_label.setText(" · ".join(meta_parts))

    def _section_title(self, text: str) -> QHBoxLayout:
        """A section heading with a trailing rule line filling the rest of
        the row, matching the mockup's `.section-title::after` treatment."""
        row = QHBoxLayout()
        row.setSpacing(8)
        label = QLabel(text)
        label.setStyleSheet(
            f"color:{get_palette().get('fg_muted').name()}; font-size:11px; font-weight:700; "
            "letter-spacing:0.5px;"
        )
        row.addWidget(label)
        rule = QFrame()
        rule.setFrameShape(QFrame.HLine)
        rule.setFixedHeight(1)
        rule.setStyleSheet(f"background:{get_palette().get('divider').name()}; border:none;")
        row.addWidget(rule, 1)
        return row

    def _build_overview_tab(self) -> None:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(0)

        scroll = QScrollArea(tab)
        scroll.setObjectName("workAssignmentOverviewScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget(scroll)
        content.setObjectName("workAssignmentOverviewContent")
        content.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 22, 24, 26)
        layout.setSpacing(18)
        scroll.setWidget(content)
        tab_layout.addWidget(scroll)

        layout.addLayout(self._section_title("ASSIGNMENT"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)

        self._number_label = QLineEdit()
        self._number_label.setPlaceholderText("(auto-generated)")

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
        self._division_combo.addItem("(none)", None)
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
            widget.setMinimumHeight(36)
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            grid.addWidget(lbl, row * 2, col)
            grid.addWidget(widget, row * 2 + 1, col, 1, col_span)

        # Same 2-column shape as the mockup's Assignment grid for the six
        # fields it actually shows; Assignment # and Op. Period are real
        # editable fields the mockup never depicted, so they get their own
        # row at the end rather than widening the grid to three columns.
        _add_field(0, 0, "Objective", self._objective_combo)
        _add_field(0, 1, "Branch", self._branch_combo)
        _add_field(1, 0, "Division / Group", self._division_combo)
        _add_field(1, 1, "Kind", self._kind_combo)
        _add_field(2, 0, "Priority", self._priority_combo)
        _add_field(2, 1, "Location / Facility", self._location_picker)
        _add_field(3, 0, "Assignment #", self._number_label)
        _add_field(3, 1, "Op. Period", self._op_period_combo)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        layout.addLayout(self._section_title("OVERVIEW"))

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
        self._objective_combo.currentIndexChanged.connect(self._refresh_header)
        self._op_period_combo.currentIndexChanged.connect(self._schedule_save)
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
        self._priority_combo.currentIndexChanged.connect(self._update_summary)
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
        lbl = QLabel("Save the Work Assignment first to add resource requirements.", placeholder)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"color: {get_palette().get('muted').name()}; font-style: italic;")
        lay = QVBoxLayout(placeholder)
        lay.addWidget(lbl)
        self._resources_placeholder = placeholder
        self._resources_tab_index = self._tabs.addTab(self._resources_placeholder, "Resources")

    def _build_hazards_tab(self) -> None:
        placeholder = QWidget()
        lbl = QLabel("Save the Work Assignment first to add hazard analysis entries.", placeholder)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"color: {get_palette().get('muted').name()}; font-style: italic;")
        lay = QVBoxLayout(placeholder)
        lay.addWidget(lbl)
        self._hazards_placeholder = placeholder
        self._hazards_tab_index = self._tabs.addTab(self._hazards_placeholder, "Hazards")

    def _build_tasks_tab(self) -> None:
        placeholder = QWidget()
        lbl = QLabel("Save the Work Assignment first to link or create tasks.", placeholder)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"color: {get_palette().get('muted').name()}; font-style: italic;")
        lay = QVBoxLayout(placeholder)
        lay.addWidget(lbl)
        self._tasks_placeholder = placeholder
        self._tasks_tab_index = self._tabs.addTab(self._tasks_placeholder, "Tasks")

    def _build_agency_requests_tab(self) -> None:
        placeholder = QWidget()
        lbl = QLabel("Save the Work Assignment first to link agency requests.", placeholder)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"color: {get_palette().get('muted').name()}; font-style: italic;")
        lay = QVBoxLayout(placeholder)
        lay.addWidget(lbl)
        self._agency_requests_placeholder = placeholder
        self._agency_requests_tab_index = self._tabs.addTab(self._agency_requests_placeholder, "Agency Requests")

    def _build_outputs_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(24, 22, 24, 26)
        layout.setSpacing(18)
        self._outputs_layout = QVBoxLayout()
        self._outputs_layout.setSpacing(10)
        layout.addLayout(self._outputs_layout)
        layout.addStretch(1)

        self._outputs_tab_index = self._tabs.addTab(tab, "Outputs")

    def _build_approvals_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(24, 22, 24, 26)
        layout.setSpacing(18)

        self._approvals_summary_label = QLabel("")
        self._approvals_summary_label.setStyleSheet(
            f"color:{get_palette().get('fg_muted').name()};"
        )
        layout.addWidget(self._approvals_summary_label)

        self._approvals_rows_layout = QVBoxLayout()
        self._approvals_rows_layout.setSpacing(8)
        layout.addLayout(self._approvals_rows_layout)
        layout.addStretch(1)

        self._approvals_tab_index = self._tabs.addTab(tab, "Approvals")

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
        self._reload_approvals()
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
        self._updated_at = wa.updated_at
        self._updated_by = str(wa.updated_by or "")
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
        editor.layout().setContentsMargins(24, 22, 24, 26)
        editor.changed.connect(self._update_summary)
        self._tabs.removeTab(self._resources_tab_index)
        self._tabs.insertTab(self._resources_tab_index, editor, "Resources")
        self._resources_placeholder = editor

    def _populate_hazard_tab(self) -> None:
        if self._work_assignment_id is None:
            return
        editor = HazardAnalysisEditor(
            self._work_assignment_id, db_path=self._db_path, parent=self
        )
        editor.layout().setContentsMargins(24, 22, 24, 26)
        editor.changed.connect(self._update_summary)
        self._tabs.removeTab(self._hazards_tab_index)
        self._tabs.insertTab(self._hazards_tab_index, editor, "Hazards")
        self._hazards_placeholder = editor

    def _populate_tasks_tab(self) -> None:
        if self._work_assignment_id is None:
            return
        panel = LinkedTasksPanel(
            self._work_assignment_id, db_path=self._db_path, parent=self
        )
        panel.layout().setContentsMargins(24, 22, 24, 26)
        panel.changed.connect(self._update_summary)
        self._tabs.removeTab(self._tasks_tab_index)
        self._tabs.insertTab(self._tasks_tab_index, panel, "Tasks")
        self._tasks_placeholder = panel

    def _populate_agency_requests_tab(self) -> None:
        if self._work_assignment_id is None:
            return
        panel = LinkedAgencyRequestsPanel(
            self._work_assignment_id, db_path=self._db_path, parent=self
        )
        panel.layout().setContentsMargins(24, 22, 24, 26)
        panel.changed.connect(self._update_summary)
        self._tabs.removeTab(self._agency_requests_tab_index)
        self._tabs.insertTab(self._agency_requests_tab_index, panel, "Agency Requests")
        self._agency_requests_placeholder = panel

    def _update_title(self) -> None:
        name = self._name_edit.text().strip() if hasattr(self, "_name_edit") else ""
        num = self._number_label.text() if hasattr(self, "_number_label") else ""
        if name:
            self.setWindowTitle(f"Work Assignment: {num} {name}".strip())
        else:
            self.setWindowTitle("Work Assignment: New")

    def _update_summary(self) -> None:
        """Refresh the Overview tab's quick-glance stat cards."""
        priority = self._priority_combo.currentText()
        self._set_stat("priority", priority, wa_priority_colors().get(priority))

        if self._work_assignment_id is None:
            for key in ("resources", "gap", "hazards", "tasks"):
                self._set_stat(key, "-")
            return

        total_req, total_assigned, total_gap, hazard_total, unresolved, link_total = (
            work_assignment_desk.meta_for(self._work_assignment_id)
        )
        self._set_stat("resources", f"{total_assigned} / {total_req}")
        self._set_stat("gap", str(total_gap), warn=total_gap > 0)
        self._set_stat("hazards", f"{unresolved} / {hazard_total}", warn=unresolved > 0)
        self._set_stat("tasks", str(link_total))

    def _set_stat(self, key: str, text: str, brushes: dict | None = None, warn: bool = False) -> None:
        _frame, value_label = self._stat_cards[key]
        value_label.setText(text)
        if brushes:
            value_label.setStyleSheet(
                f"font-size:16px; font-weight:700; color:{brushes['bg'].color().name()}; background:transparent;"
            )
        elif warn:
            value_label.setStyleSheet(
                f"font-size:16px; font-weight:700; color:{get_palette().get('danger').name()}; background:transparent;"
            )
        else:
            value_label.setStyleSheet("font-size:16px; font-weight:700; background:transparent;")

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
        self._set_save_state("dirty", "Unsaved changes")
        self._save_timer.start()

    def _set_save_state(self, state: str, text: str) -> None:
        self._save_state = state
        if not hasattr(self, "_save_state_label"):
            return
        self._save_state_label.setText(text)
        self._save_state_label.setProperty("saveState", state)
        self._save_state_label.style().unpolish(self._save_state_label)
        self._save_state_label.style().polish(self._save_state_label)

    def _auto_save(self) -> None:
        """Called by the debounce timer — save silently if a name is present."""
        data = self._collect_header_data()
        if not data.get("assignment_name"):
            self._set_save_state("dirty", "Enter a name to save")
            return  # wait until the user types a name
        self._save(quiet=True)

    def _save(self, quiet: bool = False) -> bool:
        data = self._collect_header_data()
        if not data.get("assignment_name"):
            self._set_save_state("error", "Assignment name is required")
            if not quiet:
                QMessageBox.warning(self, "Save", "Assignment name is required.")
            return False
        # Temporarily block field signals to prevent re-triggering auto-save
        self._save_timer.stop()
        self._set_save_state("saving", "Saving…")
        try:
            repo = WorkAssignmentRepository(self._db_path)
            if self._work_assignment_id is None:
                new_id = repo.create_work_assignment(data)
                self._work_assignment_id = new_id
                self._populate_resource_tab()
                self._populate_hazard_tab()
                self._populate_tasks_tab()
                self._populate_agency_requests_tab()
                repo.add_log_entry(new_id, "Work Assignment created.", entry_type="System")
                # Request Safety/OSC/PSC/LSC sign-off immediately — the
                # approvals engine notifies each resolved role as soon as
                # their step activates, so creating the assignment is what
                # puts it on their radar.
                self._start_approval_chain(quiet=True)
            else:
                repo.update_work_assignment(self._work_assignment_id, data)
                if not quiet:
                    repo.add_log_entry(self._work_assignment_id, "Work Assignment updated.", entry_type="System")
            saved_wa = repo.get_work_assignment(self._work_assignment_id)
        except Exception as exc:
            self._set_save_state("error", "Save failed")
            if not quiet:
                QMessageBox.critical(self, "Save", f"Failed to save:\n{exc}")
            return False
        if saved_wa:
            if saved_wa.assignment_number:
                self._number_label.blockSignals(True)
                self._number_label.setText(saved_wa.assignment_number)
                self._number_label.blockSignals(False)
            self._prepared_by = str(saved_wa.prepared_by or "")
            self._approved_by = str(saved_wa.approved_by or "")
            self._updated_at = saved_wa.updated_at
            self._updated_by = str(saved_wa.updated_by or "")
        self._update_title()
        self._reload_outputs()
        self._reload_approvals()
        self._refresh_header()
        saved_text = "Saved"
        if self._updated_at:
            saved_text += f" · last updated {_format_display_timestamp(self._updated_at)}"
            if self._updated_by:
                saved_text += f" by {resolve_person_name(self._updated_by)}"
        self._set_save_state("saved", saved_text)
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
            if output_type == "ICS 204":
                # ICS 204 is a multi-assignment Assignment List, assembled at
                # the IAP Package level from every work assignment in the
                # operational period — not something a single assignment can
                # generate on its own, so it isn't offered here.
                continue
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
        generate_btn.setObjectName("workAssignmentPrimaryButton")
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
        if output_type == "ICS 213RR":
            _total_req, _total_assigned, total_gap, *_rest = work_assignment_desk.meta_for(self._work_assignment_id)
            if total_gap <= 0:
                QMessageBox.information(
                    self,
                    "Generate ICS 213RR",
                    "No resource requirements on this assignment currently have a gap — "
                    "nothing to request.",
                )
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

    # ------------------------------------------------------------------
    # Approvals tab
    # ------------------------------------------------------------------

    def _current_person_record(self) -> int:
        uid = AppState.get_active_user_id()
        return int(uid) if uid and str(uid).isdigit() else 0

    def _approval_service(self) -> ApprovalService | None:
        incident_id = self._incident_id()
        if not incident_id:
            return None
        return ApprovalService(incident_id)

    def _start_approval_chain(self, *, quiet: bool = False) -> None:
        """Request sign-offs from Safety/OSC/PSC/LSC — the engine notifies
        each resolved role the moment their step activates."""
        if self._work_assignment_id is None:
            return
        service = self._approval_service()
        if service is None:
            return
        try:
            service.start("work_assignment", str(self._work_assignment_id))
        except Exception as exc:
            logger.exception("Failed to start approval chain for work assignment %s", self._work_assignment_id)
            if not quiet:
                QMessageBox.critical(self, "Request Sign-offs", f"Failed to request sign-offs:\n{exc}")

    def _reload_approvals(self) -> None:
        if not hasattr(self, "_approvals_rows_layout"):
            return
        while self._approvals_rows_layout.count():
            item = self._approvals_rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self._work_assignment_id is None:
            self._approvals_summary_label.setText("Save the work assignment first to request sign-offs.")
            self._tabs.setTabText(
                self._approvals_tab_index,
                f"Approvals  0/{len(_WA_APPROVAL_STEPS)}",
            )
            return

        service = self._approval_service()
        instance: ApprovalInstance | None = None
        try:
            if service is not None:
                instance = service.get("work_assignment", str(self._work_assignment_id))
        except Exception as exc:
            self._approvals_summary_label.setText(f"Approval details unavailable: {exc}")
            return

        steps_by_id: dict[str, StepInstance] = {s.step_id: s for s in instance.steps} if instance else {}
        total = len(_WA_APPROVAL_STEPS)
        completed = sum(1 for s in steps_by_id.values() if s.status == "completed")
        note = ""
        if instance is None:
            note = "  ·  not yet requested"
        elif instance.status == "rejected":
            note = "  ·  Rejected"
        else:
            gate = steps_by_id.get("sofr_approval")
            if gate is not None and gate.status != "completed":
                note = "  ·  Safety approval pending"
        self._approvals_summary_label.setText(f"{completed} of {total} sign-offs complete{note}")
        self._tabs.setTabText(self._approvals_tab_index, f"Approvals  {completed}/{total}")

        for step_id, label, code, is_gate in _WA_APPROVAL_STEPS:
            row = self._build_approval_row(step_id, label, code, is_gate, steps_by_id.get(step_id), instance)
            self._approvals_rows_layout.addWidget(row)

        if instance is None:
            start_btn = QPushButton("Request Sign-offs")
            start_btn.clicked.connect(lambda _checked=False: self._on_request_sign_offs())
            self._approvals_rows_layout.addWidget(start_btn, 0, Qt.AlignLeft)

    def _approval_row_status_text(
        self, step: StepInstance | None, instance: ApprovalInstance | None, is_gate: bool
    ) -> str:
        if step is None:
            return "Not Sent"
        if step.status == "completed":
            if is_gate:
                return "Rejected" if instance is not None and instance.status == "rejected" else "Approved"
            return "Reviewed"
        if step.status == "active":
            return "Pending"
        if step.status == "skipped":
            return "Skipped"
        return "Waiting"

    def _approval_row_meta(self, step: StepInstance | None) -> str:
        if step is None or step.resolved_actor_id is None:
            return ""
        name = resolve_person_name(str(step.resolved_actor_id))
        if step.status == "completed" and step.completed_at:
            return f"{name}  ·  {_format_display_timestamp(step.completed_at)}"
        if step.status == "active":
            return f"Awaiting {name}"
        return name

    def _build_approval_row(
        self,
        step_id: str,
        label: str,
        code: str,
        is_gate: bool,
        step: StepInstance | None,
        instance: ApprovalInstance | None,
    ) -> QFrame:
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

        title = QLabel(f"{label} ({code})")
        title.setStyleSheet("font-weight:700;")
        layout.addWidget(title, 1)

        status_text = self._approval_row_status_text(step, instance, is_gate)
        badge = QLabel(status_text)
        badge.setAlignment(Qt.AlignCenter)
        step_colors = approval_step_status_colors().get(step.status if step else "waiting")
        badge_bg = step_colors["bg"].color().name() if step_colors else get_palette().get("ctrl_border").name()
        badge.setStyleSheet(
            f"background:{badge_bg}; color:{get_palette().get('fg').name()}; "
            "padding:2px 10px; border-radius:4px; font-weight:700;"
        )
        layout.addWidget(badge)

        meta = QLabel(self._approval_row_meta(step))
        meta.setStyleSheet(f"color:{get_palette().get('fg_muted').name()};")
        layout.addWidget(meta)

        if step is not None and step.status == "active":
            if step.resolved_actor_id is None:
                assign_btn = QPushButton("Assign…")
                assign_btn.setToolTip(
                    "Nobody currently holds this role (or the escalation chain up to "
                    "Incident Commander is vacant) — pick who should sign off."
                )
                assign_btn.clicked.connect(
                    lambda _checked=False, sid=step_id, lbl=label: self._on_assign_approval_step(sid, lbl)
                )
                layout.addWidget(assign_btn)
            person_record = self._current_person_record()
            if step.resolved_actor_id == person_record:
                if is_gate:
                    approve_btn = QPushButton("Approve")
                    approve_btn.clicked.connect(
                        lambda _checked=False, sid=step_id: self._act_on_approval_step(sid, "approved")
                    )
                    layout.addWidget(approve_btn)
                    reject_btn = QPushButton("Reject")
                    reject_btn.clicked.connect(
                        lambda _checked=False, sid=step_id: self._act_on_approval_step(sid, "rejected")
                    )
                    layout.addWidget(reject_btn)
                else:
                    review_btn = QPushButton("Mark Reviewed")
                    review_btn.clicked.connect(
                        lambda _checked=False, sid=step_id: self._act_on_approval_step(sid, "acknowledged")
                    )
                    layout.addWidget(review_btn)
            if step.resolved_actor_id is not None:
                send_label = "Send for Approval" if is_gate else "Send for Review"
                send_btn = QPushButton(send_label)
                send_btn.clicked.connect(lambda _checked=False, sid=step_id: self._send_for_approval(sid))
                layout.addWidget(send_btn)

        return row

    def _on_request_sign_offs(self) -> None:
        self._start_approval_chain()
        self._reload_approvals()

    def _on_assign_approval_step(self, step_id: str, step_label: str) -> None:
        if self._work_assignment_id is None:
            return
        from modules.approvals.panels.assign_step_dialog import AssignStepDialog

        dlg = AssignStepDialog(step_label, self)
        if not dlg.exec():
            return
        person_record = dlg.selected_person_record()
        if not person_record:
            return
        service = self._approval_service()
        if service is None:
            return
        try:
            instance = service.get("work_assignment", str(self._work_assignment_id))
            if instance is None:
                raise RuntimeError("Sign-offs have not been requested yet.")
            service.assign_step(instance, step_id, person_record)
        except Exception as exc:
            QMessageBox.critical(self, "Assign Failed", str(exc))
            return
        self._reload_approvals()

    def _send_for_approval(self, step_id: str) -> None:
        """Manual nudge — re-send the notification for a step that's already
        active and resolved (the engine already notified its actor once,
        automatically, the moment the step activated)."""
        if self._work_assignment_id is None:
            return
        service = self._approval_service()
        if service is None:
            return
        try:
            instance = service.get("work_assignment", str(self._work_assignment_id))
            if instance is None:
                service.start("work_assignment", str(self._work_assignment_id))
            else:
                service.notify_step(instance, step_id)
        except Exception as exc:
            QMessageBox.critical(self, "Send Notification", f"Failed to send notification:\n{exc}")
            return
        self._reload_approvals()

    def _act_on_approval_step(self, step_id: str, action: str) -> None:
        if self._work_assignment_id is None:
            return
        notes = None
        if action == "rejected":
            reason, ok = QInputDialog.getText(
                self, "Reject", "Why is this work assignment's safety approval being rejected?"
            )
            if not ok:
                return
            notes = reason.strip() or None
        service = self._approval_service()
        if service is None:
            return
        try:
            instance = service.get("work_assignment", str(self._work_assignment_id))
            if instance is None:
                raise RuntimeError("Sign-offs have not been requested yet.")
            person_record = self._current_person_record()
            service.sign(instance, step_id, person_record, action, notes=notes)
        except Exception as exc:
            QMessageBox.critical(self, "Approval Failed", str(exc))
            return
        self._reload_approvals()

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        super().closeEvent(event)
