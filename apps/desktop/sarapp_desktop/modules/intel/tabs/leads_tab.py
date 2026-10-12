"""LeadsTab — table view for Intel leads."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QDialog, QFormLayout,
    QTextEdit, QDialogButtonBox, QInputDialog, QStackedWidget,
    QGroupBox, QCheckBox, QScrollArea,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush

from modules.intel.models.leads import (
    Lead, LeadStatus, LeadPriority, LeadSourceCategory,
    LEAD_STATUSES, LEAD_PRIORITIES, LEAD_SOURCE_CATEGORIES,
    SOURCE_RELIABILITY_VALUES, INFORMATION_CONFIDENCE_VALUES,
    _CATEGORY_TO_SOURCE_TYPE,
)
from modules.intel.services.intel_service import IntelService
from utils.table_view_styles import apply_statusboard_table_behavior
from utils.styles import intel_lead_status_colors, get_palette, subscribe_theme


def _row_color(lead: Lead) -> QBrush | None:
    colors = intel_lead_status_colors()
    status = (lead.status or "").lower()
    if not lead.assigned_to and lead.priority in ("Critical", "High"):
        return colors["unassigned_high"]["bg"]
    if not lead.assigned_to:
        return colors["unassigned"]["bg"]
    entry = colors.get(status)
    return entry["bg"] if entry else None


def _btn(label: str, callback, width: int = 52) -> QPushButton:
    b = QPushButton(label)
    b.setFixedHeight(22)
    b.setFixedWidth(width)
    b.clicked.connect(callback)
    return b


def _color_blob(hex_color: str, label: str) -> str:
    return (
        f'<span style="color: {hex_color}; font-size: 16px; vertical-align: middle;">&#9679;</span> '
        f'<span style="vertical-align: middle;">{label}</span>'
    )


def _field(placeholder: str = "") -> QLineEdit:
    w = QLineEdit()
    if placeholder:
        w.setPlaceholderText(placeholder)
    return w


def _combo(items: list[str], default: str = "") -> QComboBox:
    w = QComboBox()
    w.addItems(items)
    if default:
        w.setCurrentText(default)
    return w


class _NewLeadDialog(QDialog):
    """Structured lead creation dialog with source-category-driven fields."""

    def __init__(self, service: IntelService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Lead")
        self.setMinimumWidth(520)
        self.setMinimumHeight(560)
        self.lead: Lead | None = None
        self.subject_to_create = None  # caller creates Subject first if set

        self._service = service
        self._teams: list[dict] = self._load_teams()

        # Outer layout uses a scroll area so the form fits any monitor size
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 8)
        layout.setSpacing(10)
        scroll.setWidget(container)
        outer.addWidget(scroll)

        # ── Common top fields ──────────────────────────────────────────
        form_top = QFormLayout()
        form_top.setSpacing(8)

        self._title = _field("Brief description (required)")
        form_top.addRow("Title *", self._title)

        self._summary = QTextEdit()
        self._summary.setPlaceholderText("Detailed summary")
        self._summary.setMinimumHeight(56)
        self._summary.setMaximumHeight(100)
        form_top.addRow("Summary", self._summary)

        self._priority = _combo(LEAD_PRIORITIES, LeadPriority.MEDIUM)
        form_top.addRow("Priority", self._priority)

        layout.addLayout(form_top)

        # ── Source section ─────────────────────────────────────────────
        src_box = QGroupBox("Source")
        src_layout = QVBoxLayout(src_box)
        src_layout.setSpacing(8)

        cat_row = QHBoxLayout()
        cat_row.addWidget(QLabel("Category:"))
        self._source_cat = QComboBox()
        self._source_cat.addItems(LEAD_SOURCE_CATEGORIES)
        self._source_cat.currentIndexChanged.connect(self._on_category_changed)
        cat_row.addWidget(self._source_cat)
        cat_row.addStretch()
        src_layout.addLayout(cat_row)

        self._source_stack = QStackedWidget()
        self._source_stack.addWidget(self._build_team_page())
        self._source_stack.addWidget(self._build_staff_page())
        self._source_stack.addWidget(self._build_agency_page())
        self._source_stack.addWidget(self._build_public_tip_page())
        self._source_stack.addWidget(self._build_other_page())
        src_layout.addWidget(self._source_stack)
        layout.addWidget(src_box)

        # ── Report quality ─────────────────────────────────────────────
        quality_box = QGroupBox("Report Quality")
        q_form = QFormLayout(quality_box)
        q_form.setSpacing(8)
        self._reliability = _combo([""] + SOURCE_RELIABILITY_VALUES)
        self._confidence = _combo([""] + INFORMATION_CONFIDENCE_VALUES)
        q_form.addRow("Source Reliability", self._reliability)
        q_form.addRow("Information Confidence", self._confidence)
        layout.addWidget(quality_box)

        # ── Location + Assignment ─────────────────────────────────────
        form_bot = QFormLayout()
        form_bot.setSpacing(8)
        self._location = _field("Optional plain-text location or address")
        form_bot.addRow("Location", self._location)
        self._assigned_to = _field("Leave blank if unassigned")
        form_bot.addRow("Assign To", self._assigned_to)
        self._notes = QTextEdit()
        self._notes.setPlaceholderText("Optional notes")
        self._notes.setMaximumHeight(80)
        form_bot.addRow("Notes", self._notes)
        layout.addLayout(form_bot)

        # ── Buttons ───────────────────────────────────────────────────
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_save)
        btns.rejected.connect(self.reject)
        outer.addWidget(btns)

    # ------------------------------------------------------------------
    # Source-specific pages

    def _build_team_page(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        f.setSpacing(6)
        if self._teams:
            self._team_combo = QComboBox()
            self._team_combo.addItem("— Select team —", None)
            for t in self._teams:
                label = t.get("callsign") or t.get("name", "")
                if t.get("name") and t.get("callsign"):
                    label = f"{t['callsign']} — {t['name']}"
                self._team_combo.addItem(label, t.get("id") or t.get("team_id"))
            f.addRow("Team", self._team_combo)
        else:
            self._team_name_text = _field("Team name or callsign")
            f.addRow("Team", self._team_name_text)
        self._team_member = _field("Reporting member (optional)")
        self._team_channel = _field("Channel / method (optional)")
        f.addRow("Reporting Member", self._team_member)
        f.addRow("Contact Channel", self._team_channel)
        return w

    def _build_staff_page(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        f.setSpacing(6)
        self._staff_name = _field("Name or role")
        self._staff_section = _field("Section or unit (optional)")
        self._staff_contact = _field("Contact method (optional)")
        f.addRow("Staff Member", self._staff_name)
        f.addRow("Section / Unit", self._staff_section)
        f.addRow("Contact Method", self._staff_contact)
        return w

    def _build_agency_page(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        f.setSpacing(6)
        self._agency_name = _field("Agency or organization (required)")
        self._agency_contact = _field("Representative name — creates Contact Subject if filled")
        self._agency_role = _field("Role or title (optional)")
        self._agency_phone = _field("Phone (optional)")
        self._agency_email = _field("Email (optional)")
        self._agency_method = _field("Preferred contact method (optional)")
        self._agency_notes = QTextEdit()
        self._agency_notes.setPlaceholderText("Source notes (optional)")
        self._agency_notes.setMaximumHeight(60)
        f.addRow("Agency *", self._agency_name)
        f.addRow("Representative", self._agency_contact)
        f.addRow("Role / Title", self._agency_role)
        f.addRow("Phone", self._agency_phone)
        f.addRow("Email", self._agency_email)
        f.addRow("Contact Method", self._agency_method)
        f.addRow("Source Notes", self._agency_notes)
        return w

    def _build_public_tip_page(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        f.setSpacing(6)
        self._tip_name = _field("Informant name (required)")
        self._tip_phone = _field("Phone (optional)")
        self._tip_email = _field("Email (optional)")
        self._tip_address = _field("Address (optional)")
        self._tip_context = _field("Relationship or context (optional)")
        self._tip_subject_type = _combo(["Reporting Party", "Witness", "Contact"], "Reporting Party")
        tip_note = QLabel("A Subject will be created for this informant.")
        tip_note.setStyleSheet("color: palette(placeholderText); font-style: italic; font-size: 11px;")
        f.addRow("Name *", self._tip_name)
        f.addRow("Phone", self._tip_phone)
        f.addRow("Email", self._tip_email)
        f.addRow("Address", self._tip_address)
        f.addRow("Relationship", self._tip_context)
        f.addRow("Subject Type", self._tip_subject_type)
        f.addRow("", tip_note)
        return w

    def _build_other_page(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        f.setSpacing(6)
        self._other_label = _field("Source label (optional)")
        self._other_contact_name = _field("Contact name (optional)")
        self._other_contact_info = _field("Contact info (optional)")
        self._other_notes = QTextEdit()
        self._other_notes.setPlaceholderText("Source notes (optional)")
        self._other_notes.setMaximumHeight(60)
        self._other_create_subject = QCheckBox("Create Contact Subject for this contact")
        f.addRow("Source Label", self._other_label)
        f.addRow("Contact Name", self._other_contact_name)
        f.addRow("Contact Info", self._other_contact_info)
        f.addRow("Source Notes", self._other_notes)
        f.addRow("", self._other_create_subject)
        return w

    # ------------------------------------------------------------------

    def _load_teams(self) -> list[dict]:
        if not (self._service and self._service.incident_id):
            return []
        try:
            from utils.api_client import api_client
            result = api_client.get(f"/api/incidents/{self._service.incident_id}/operations/teams")
            return result if isinstance(result, list) else []
        except Exception:
            return []

    def _on_category_changed(self, index: int) -> None:
        self._source_stack.setCurrentIndex(index)

    def _on_save(self) -> None:
        title = self._title.text().strip()
        if not title:
            self._title.setStyleSheet(f"border: 1px solid {get_palette()['error'].name()};")
            return

        cat = self._source_cat.currentText()
        source_type = _CATEGORY_TO_SOURCE_TYPE.get(cat, "Other")

        # Collect source-specific fields
        source_team_id = None
        source_team_name = None
        source_staff_id = None
        source_agency = None
        source_role = None
        source_contact_name = None
        source_phone = None
        source_email = None
        source_address = None
        source_contact_method = None
        source_notes_val = None
        reported_by = None

        if cat == LeadSourceCategory.TEAM:
            if self._teams and hasattr(self, "_team_combo"):
                tid = self._team_combo.currentData()
                tname = self._team_combo.currentText()
                if tid:
                    source_team_id = int(tid) if str(tid).isdigit() else None
                    source_team_name = tname
                    reported_by = tname
            elif hasattr(self, "_team_name_text"):
                source_team_name = self._team_name_text.text().strip() or None
                reported_by = source_team_name
            source_contact_name = self._team_member.text().strip() or None
            source_contact_method = self._team_channel.text().strip() or None

        elif cat == LeadSourceCategory.STAFF:
            source_contact_name = self._staff_name.text().strip() or None
            source_agency = self._staff_section.text().strip() or None
            source_contact_method = self._staff_contact.text().strip() or None
            reported_by = source_contact_name

        elif cat == LeadSourceCategory.AGENCY_LIAISON:
            source_agency = self._agency_name.text().strip() or None
            source_contact_name = self._agency_contact.text().strip() or None
            source_role = self._agency_role.text().strip() or None
            source_phone = self._agency_phone.text().strip() or None
            source_email = self._agency_email.text().strip() or None
            source_contact_method = self._agency_method.text().strip() or None
            source_notes_val = self._agency_notes.toPlainText().strip() or None
            reported_by = source_contact_name or source_agency

        elif cat == LeadSourceCategory.PUBLIC_TIP:
            if not self._tip_name.text().strip():
                self._tip_name.setStyleSheet(f"border: 1px solid {get_palette()['error'].name()};")
                return
            source_contact_name = self._tip_name.text().strip()
            source_phone = self._tip_phone.text().strip() or None
            source_email = self._tip_email.text().strip() or None
            source_address = self._tip_address.text().strip() or None
            source_role = self._tip_context.text().strip() or None
            reported_by = source_contact_name

        elif cat == LeadSourceCategory.OTHER:
            source_agency = self._other_label.text().strip() or None
            source_contact_name = self._other_contact_name.text().strip() or None
            source_contact_method = self._other_contact_info.text().strip() or None
            source_notes_val = self._other_notes.toPlainText().strip() or None
            reported_by = source_contact_name or source_agency

        # Build human-readable source_display
        source_display = self._build_source_display(
            cat, source_team_name, source_contact_name, source_agency
        )

        reliability = self._reliability.currentText() or None
        confidence = self._confidence.currentText() or None

        contact_info_parts = [p for p in (source_phone, source_email, source_contact_method) if p]

        self.lead = Lead(
            id="", incident_id="",
            title=title,
            summary=self._summary.toPlainText().strip() or None,
            source_type=source_type,
            source_category=cat,
            source_display=source_display,
            source_team_id=source_team_id,
            source_team_name=source_team_name,
            source_agency=source_agency,
            source_role=source_role,
            source_contact_name=source_contact_name,
            source_phone=source_phone,
            source_email=source_email,
            source_address=source_address,
            source_contact_method=source_contact_method,
            source_notes=source_notes_val,
            source_reliability=reliability,
            information_confidence=confidence,
            reported_by=reported_by,
            contact_info=" / ".join(contact_info_parts) or None,
            location_text=self._location.text().strip() or None,
            priority=self._priority.currentText(),
            assigned_to=self._assigned_to.text().strip() or None,
            notes=self._notes.toPlainText().strip() or None,
        )

        # Build subject_to_create if applicable
        self.subject_to_create = self._build_subject(cat, source_contact_name)

        self.accept()

    def _build_source_display(
        self,
        cat: str,
        team_name: str | None,
        contact_name: str | None,
        agency: str | None,
    ) -> str | None:
        if cat == LeadSourceCategory.TEAM:
            return team_name or None
        if cat == LeadSourceCategory.STAFF:
            return contact_name or None
        if cat == LeadSourceCategory.AGENCY_LIAISON:
            if agency and contact_name:
                return f"{agency} / {contact_name}"
            return agency or contact_name or None
        if cat == LeadSourceCategory.PUBLIC_TIP:
            return contact_name or "Public Tip"
        if cat == LeadSourceCategory.OTHER:
            return agency or contact_name or None
        return None

    def _build_subject(self, cat: str, contact_name: str | None):
        from modules.intel.models.subjects import Subject, SubjectType

        if cat == LeadSourceCategory.PUBLIC_TIP and self._tip_name.text().strip():
            type_map = {
                "Reporting Party": SubjectType.REPORTING_PARTY,
                "Witness": SubjectType.WITNESS,
                "Contact": SubjectType.CONTACT,
            }
            subj_type = type_map.get(self._tip_subject_type.currentText(), SubjectType.REPORTING_PARTY)
            return Subject(
                id="", incident_id="",
                subject_type=subj_type,
                name=self._tip_name.text().strip(),
                phone=self._tip_phone.text().strip() or None,
                email=self._tip_email.text().strip() or None,
                address=self._tip_address.text().strip() or None,
                initial_report=self._tip_context.text().strip() or None,
            )

        if cat == LeadSourceCategory.AGENCY_LIAISON and contact_name:
            return Subject(
                id="", incident_id="",
                subject_type=SubjectType.CONTACT,
                name=contact_name,
                organization=self._agency_name.text().strip() or None,
                phone=self._agency_phone.text().strip() or None,
                email=self._agency_email.text().strip() or None,
            )

        if cat == LeadSourceCategory.OTHER and self._other_create_subject.isChecked() and contact_name:
            return Subject(
                id="", incident_id="",
                subject_type=SubjectType.CONTACT,
                name=contact_name,
            )

        return None


class LeadsTab(QWidget):
    open_lead_detail = Signal(object)
    convert_lead = Signal(object)

    _COLS = ["#", "Title", "Priority", "Status", "Source", "Confidence", "Location", "Assigned To", "Updated", "Actions"]

    def __init__(self, service: IntelService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._leads: list[Lead] = []
        self._filtered: list[Lead] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        # ── Toolbar row 1: title + primary filters ─────────────────────
        toolbar = QHBoxLayout()
        title_lbl = QLabel("Leads")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: 700; color: palette(windowText);")

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search…")
        self._search.setFixedWidth(180)
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

        toolbar.addWidget(title_lbl)
        toolbar.addStretch()
        toolbar.addWidget(self._search)
        toolbar.addWidget(self._status_filter)
        toolbar.addWidget(self._priority_filter)
        toolbar.addWidget(new_btn)
        layout.addLayout(toolbar)

        # ── Toolbar row 2: additional filters ─────────────────────────
        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)

        self._source_filter = QComboBox()
        self._source_filter.addItem("All Sources")
        self._source_filter.addItems(LEAD_SOURCE_CATEGORIES)
        self._source_filter.currentTextChanged.connect(self._apply_filter)

        self._confidence_filter = QComboBox()
        self._confidence_filter.addItem("All Confidence")
        self._confidence_filter.addItems(INFORMATION_CONFIDENCE_VALUES)
        self._confidence_filter.currentTextChanged.connect(self._apply_filter)

        self._location_filter = QComboBox()
        self._location_filter.addItems(["Any Location", "Has Location", "No Location"])
        self._location_filter.currentTextChanged.connect(self._apply_filter)

        filter_row.addStretch()
        filter_row.addWidget(QLabel("Source:"))
        filter_row.addWidget(self._source_filter)
        filter_row.addWidget(QLabel("Confidence:"))
        filter_row.addWidget(self._confidence_filter)
        filter_row.addWidget(QLabel("Location:"))
        filter_row.addWidget(self._location_filter)
        layout.addLayout(filter_row)

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
        self._legend = QLabel()
        self._legend.setTextFormat(Qt.RichText)
        self._legend.setStyleSheet("font-size: 11px; color: palette(placeholderText);")
        layout.addWidget(self._legend)
        self._update_legend()

        subscribe_theme(self, self._on_theme_changed)
        self.refresh()

    def _update_legend(self) -> None:
        colors = intel_lead_status_colors()
        self._legend.setText(
            "  ".join([
                _color_blob(colors["unassigned_high"]["fg"].color().name(), "Unassigned Critical / High"),
                _color_blob(colors["unassigned"]["fg"].color().name(), "Unassigned"),
                _color_blob(colors["new"]["fg"].color().name(), "New"),
                _color_blob(colors["assigned"]["fg"].color().name(), "Assigned"),
                _color_blob(colors["converted"]["fg"].color().name(), "Converted"),
                _color_blob(colors["closed"]["fg"].color().name(), "Closed"),
            ])
        )

    def _on_theme_changed(self, *_: object) -> None:
        self._update_legend()
        self._render()

    def refresh(self) -> None:
        if self._service is None:
            return
        self._leads = self._service.leads.list()
        self._apply_filter()

    def _apply_filter(self) -> None:
        q = self._search.text().lower()
        status_sel = self._status_filter.currentText()
        priority_sel = self._priority_filter.currentText()
        source_sel = self._source_filter.currentText()
        conf_sel = self._confidence_filter.currentText()
        loc_sel = self._location_filter.currentText()

        self._filtered = [
            l for l in self._leads
            if (not q or q in l.title.lower() or q in (l.summary or "").lower())
            and (status_sel == "All Statuses" or l.status == status_sel)
            and (priority_sel == "All Priorities" or l.priority == priority_sel)
            and (source_sel == "All Sources" or l.source_category == source_sel)
            and (conf_sel == "All Confidence" or l.information_confidence == conf_sel)
            and (loc_sel == "Any Location"
                 or (loc_sel == "Has Location" and bool(l.location_text))
                 or (loc_sel == "No Location" and not l.location_text))
        ]
        self._render()

    def _render(self) -> None:
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(self._filtered))
        for row, l in enumerate(self._filtered):
            source_display = l.source_display or l.source_category or l.source_type or ""
            location_short = (l.location_text or "")
            if len(location_short) > 50:
                location_short = location_short[:48] + "…"
            cells = [
                l.display_number,
                l.title,
                l.priority or "",
                l.status or "",
                source_display,
                l.information_confidence or "",
                location_short,
                l.assigned_to or "Unassigned",
                l.updated_at[:16].replace("T", " ") if l.updated_at else "",
            ]
            brush = _row_color(l)
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

        for col in (0, 2, 3, 4, 5, 6, 7, 8):
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
        dlg = _NewLeadDialog(self._service, self)
        if dlg.exec() == QDialog.Accepted and dlg.lead:
            lead = dlg.lead
            # Create Subject first if the dialog produced one
            if dlg.subject_to_create:
                dlg.subject_to_create.incident_id = self._service.incident_id or ""
                created_subj = self._service.subjects.create(dlg.subject_to_create)
                if created_subj:
                    lead.source_subject_id = created_subj.id
            self._service.leads.create(lead)
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
