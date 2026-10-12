"""LeadDetailWindow — modeless window for viewing and managing a single Lead."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QScrollArea, QFrame, QDialog,
    QFormLayout, QLineEdit, QComboBox, QDialogButtonBox,
)
from PySide6.QtCore import Qt, Signal

from modules.intel.models.leads import (
    Lead, LeadStatus, LeadPriority, LeadSourceCategory,
    LEAD_SOURCE_CATEGORIES, SOURCE_RELIABILITY_VALUES, INFORMATION_CONFIDENCE_VALUES,
)
from modules.intel.widgets.status_chip import StatusChip
from modules.intel.services.intel_service import IntelService


class _FieldRow(QWidget):
    def __init__(self, label: str, value: str | None, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        lbl = QLabel(label + ":")
        lbl.setStyleSheet("font-weight: 600; min-width: 140px;")
        lbl.setAlignment(Qt.AlignRight | Qt.AlignTop)
        val = QLabel(value or "—")
        val.setWordWrap(True)
        layout.addWidget(lbl)
        layout.addWidget(val, 1)


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("font-weight: 700; font-size: 12px; color: palette(windowText);")
    return lbl


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    return f


class LeadDetailWindow(QMainWindow):
    """Modeless detail window for a single Lead."""

    lead_updated = Signal(object)

    def __init__(
        self,
        lead: Lead,
        service: IntelService,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._lead = lead
        self._service = service

        self.setWindowTitle(f"{lead.display_number}: {lead.title}")
        self.resize(700, 560)
        self.setAttribute(Qt.WA_DeleteOnClose)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setWidget(self._build_body())
        root.addWidget(self._scroll)

        root.addWidget(self._build_action_bar())

    def _build_header(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: palette(dark); padding: 12px;")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)

        num_lbl = QLabel(self._lead.display_number)
        num_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: palette(placeholderText);")
        title_lbl = QLabel(self._lead.title)
        title_lbl.setStyleSheet("font-size: 18px; font-weight: 700; color: palette(bright-text);")
        priority_chip = StatusChip(self._lead.priority)
        status_chip = StatusChip(self._lead.status)

        layout.addWidget(num_lbl)
        layout.addWidget(title_lbl)
        layout.addStretch()
        layout.addWidget(priority_chip)
        layout.addWidget(status_chip)
        return w

    def _build_body(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(8)

        lead = self._lead

        if lead.summary:
            summary_lbl = QLabel(lead.summary)
            summary_lbl.setWordWrap(True)
            summary_lbl.setStyleSheet("font-size: 13px; margin-bottom: 8px;")
            layout.addWidget(summary_lbl)

        # ── Source ─────────────────────────────────────────────────────
        layout.addWidget(_sep())
        layout.addWidget(_section_label("Source Information"))

        if lead.source_category:
            layout.addWidget(_FieldRow("Category", lead.source_category))

        if lead.source_display:
            layout.addWidget(_FieldRow("Source", lead.source_display))
        elif lead.source_type:
            layout.addWidget(_FieldRow("Source Type", lead.source_type))

        # Category-specific fields
        cat = lead.source_category or ""
        if cat == LeadSourceCategory.TEAM:
            if lead.source_team_name:
                layout.addWidget(_FieldRow("Team", lead.source_team_name))
            if lead.source_contact_name:
                layout.addWidget(_FieldRow("Reporting Member", lead.source_contact_name))
            if lead.source_contact_method:
                layout.addWidget(_FieldRow("Channel", lead.source_contact_method))

        elif cat == LeadSourceCategory.STAFF:
            if lead.source_contact_name:
                layout.addWidget(_FieldRow("Staff Member", lead.source_contact_name))
            if lead.source_agency:
                layout.addWidget(_FieldRow("Section / Unit", lead.source_agency))
            if lead.source_contact_method:
                layout.addWidget(_FieldRow("Contact Method", lead.source_contact_method))

        elif cat == LeadSourceCategory.AGENCY_LIAISON:
            if lead.source_agency:
                layout.addWidget(_FieldRow("Agency", lead.source_agency))
            if lead.source_contact_name:
                layout.addWidget(_FieldRow("Representative", lead.source_contact_name))
            if lead.source_role:
                layout.addWidget(_FieldRow("Role / Title", lead.source_role))
            if lead.source_phone:
                layout.addWidget(_FieldRow("Phone", lead.source_phone))
            if lead.source_email:
                layout.addWidget(_FieldRow("Email", lead.source_email))
            if lead.source_contact_method:
                layout.addWidget(_FieldRow("Contact Method", lead.source_contact_method))
            if lead.source_subject_id:
                self._add_subject_link(layout, lead.source_subject_id)
            if lead.source_notes:
                layout.addWidget(_FieldRow("Source Notes", lead.source_notes))

        elif cat == LeadSourceCategory.PUBLIC_TIP:
            if lead.source_contact_name:
                layout.addWidget(_FieldRow("Informant", lead.source_contact_name))
            if lead.source_phone:
                layout.addWidget(_FieldRow("Phone", lead.source_phone))
            if lead.source_email:
                layout.addWidget(_FieldRow("Email", lead.source_email))
            if lead.source_address:
                layout.addWidget(_FieldRow("Address", lead.source_address))
            if lead.source_role:
                layout.addWidget(_FieldRow("Relationship", lead.source_role))
            if lead.source_subject_id:
                self._add_subject_link(layout, lead.source_subject_id)

        else:
            # Legacy / Other — show reported_by and contact_info fallbacks
            if lead.reported_by:
                layout.addWidget(_FieldRow("Reported By", lead.reported_by))
            if lead.contact_info:
                layout.addWidget(_FieldRow("Contact Info", lead.contact_info))
            if lead.source_contact_name:
                layout.addWidget(_FieldRow("Contact Name", lead.source_contact_name))
            if lead.source_notes:
                layout.addWidget(_FieldRow("Source Notes", lead.source_notes))

        # ── Report quality ─────────────────────────────────────────────
        if lead.source_reliability or lead.information_confidence:
            layout.addWidget(_sep())
            layout.addWidget(_section_label("Report Quality"))
            if lead.source_reliability:
                layout.addWidget(_FieldRow("Source Reliability", lead.source_reliability))
            if lead.information_confidence:
                layout.addWidget(_FieldRow("Information Confidence", lead.information_confidence))

        # ── Location ──────────────────────────────────────────────────
        layout.addWidget(_sep())
        layout.addWidget(_section_label("Location"))
        layout.addWidget(_FieldRow("Location", lead.location_text))

        # ── Assignment ────────────────────────────────────────────────
        layout.addWidget(_sep())
        layout.addWidget(_section_label("Assignment"))
        layout.addWidget(_FieldRow("Assigned To", lead.assigned_to))
        layout.addWidget(_FieldRow("Status", lead.status))

        # ── Conversion ────────────────────────────────────────────────
        if lead.converted_to_type:
            layout.addWidget(_sep())
            layout.addWidget(_section_label("Conversion"))
            self._add_converted_target(layout, lead)

        # ── Notes ─────────────────────────────────────────────────────
        if lead.notes:
            layout.addWidget(_sep())
            layout.addWidget(_section_label("Notes"))
            notes_lbl = QLabel(lead.notes)
            notes_lbl.setWordWrap(True)
            layout.addWidget(notes_lbl)

        layout.addWidget(_sep())
        layout.addWidget(_FieldRow("Created", lead.created_at[:16].replace("T", "  ")))
        layout.addWidget(_FieldRow("Updated", lead.updated_at[:16].replace("T", "  ")))

        layout.addStretch()
        return w

    def _add_subject_link(self, layout: QVBoxLayout, subject_id: str) -> None:
        """Add a clickable link to the source Subject if it can be resolved."""
        try:
            subject = self._service.subjects.get(subject_id)
        except Exception:
            subject = None
        if subject:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 2, 0, 2)
            lbl = QLabel("Source Subject:")
            lbl.setStyleSheet("font-weight: 600; min-width: 140px;")
            lbl.setAlignment(Qt.AlignRight | Qt.AlignTop)
            link_btn = QPushButton(f"{subject.name} — {subject.subject_type}")
            link_btn.setFlat(True)
            link_btn.setStyleSheet("color: palette(link); text-decoration: underline; border: none; text-align: left;")
            link_btn.clicked.connect(lambda: self._open_subject(subject))
            rl.addWidget(lbl)
            rl.addWidget(link_btn, 1)
            layout.addWidget(row)
        else:
            layout.addWidget(_FieldRow("Source Subject", subject_id))

    def _add_converted_target(self, layout: QVBoxLayout, lead: Lead) -> None:
        """Show the converted target with a clickable link where resolvable."""
        target_type = lead.converted_to_type or ""
        target_id = lead.converted_to_id

        layout.addWidget(_FieldRow("Converted To", target_type.title()))

        if not target_id:
            return

        resolved_label = None
        resolved_obj = None

        try:
            if target_type == "item":
                item = self._service.items.get(target_id)
                if item:
                    resolved_label = f"{item.title} ({item.item_type})"
                    resolved_obj = ("item", item)
            elif target_type == "subject":
                subj = self._service.subjects.get(target_id)
                if subj:
                    resolved_label = f"{subj.name} — {subj.subject_type}"
                    resolved_obj = ("subject", subj)
        except Exception:
            pass

        if resolved_obj:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 2, 0, 2)
            lbl = QLabel("Target Record:")
            lbl.setStyleSheet("font-weight: 600; min-width: 140px;")
            lbl.setAlignment(Qt.AlignRight | Qt.AlignTop)
            link_btn = QPushButton(resolved_label)
            link_btn.setFlat(True)
            link_btn.setStyleSheet("color: palette(link); text-decoration: underline; border: none; text-align: left;")
            kind, obj = resolved_obj
            link_btn.clicked.connect(lambda: self._open_target(kind, obj))
            rl.addWidget(lbl)
            rl.addWidget(link_btn, 1)
            layout.addWidget(row)
        else:
            layout.addWidget(_FieldRow("Target ID", target_id))

    def _open_subject(self, subject) -> None:
        from modules.intel.windows.subject_detail_window import SubjectDetailWindow
        win = SubjectDetailWindow(subject, self._service, parent=self)
        win.show()
        win.raise_()

    def _open_target(self, kind: str, obj) -> None:
        if kind == "item":
            from modules.intel.windows.intel_item_detail_window import IntelItemDetailWindow
            win = IntelItemDetailWindow(obj, self._service, parent=self)
            win.show()
            win.raise_()
        elif kind == "subject":
            self._open_subject(obj)

    def _build_action_bar(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: palette(window); border-top: 1px solid palette(mid);")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(8)

        assign_btn = QPushButton("Assign")
        assign_btn.clicked.connect(self._assign)

        self._convert_btn = QPushButton("Convert →")
        self._convert_btn.clicked.connect(self._convert)
        self._convert_btn.setEnabled(self._lead.is_open)

        self._close_btn = QPushButton("Close Lead")
        self._close_btn.clicked.connect(self._close_lead)
        self._close_btn.setEnabled(self._lead.is_open)

        self._reject_btn = QPushButton("Reject")
        self._reject_btn.clicked.connect(self._reject)
        self._reject_btn.setEnabled(self._lead.is_open)

        layout.addStretch()
        layout.addWidget(assign_btn)
        layout.addWidget(self._convert_btn)
        layout.addWidget(self._close_btn)
        layout.addWidget(self._reject_btn)
        return w

    def _refresh_body(self) -> None:
        """Rebuild the scrollable body and update action button states."""
        self._scroll.setWidget(self._build_body())
        is_open = self._lead.is_open
        self._convert_btn.setEnabled(is_open)
        self._close_btn.setEnabled(is_open)
        self._reject_btn.setEnabled(is_open)

    def _assign(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(
            self, "Assign Lead", "Assign to:", text=self._lead.assigned_to or ""
        )
        if ok:
            updated = self._service.leads.update(self._lead.id, {
                "assigned_to": name.strip() or None,
                "status": LeadStatus.ASSIGNED if name.strip() else self._lead.status,
            })
            if updated:
                self._lead = updated
                self.lead_updated.emit(updated)

    def _convert(self) -> None:
        from PySide6.QtWidgets import QInputDialog, QMessageBox
        choices = ["item", "subject", "assessment"]
        choice, ok = QInputDialog.getItem(
            self, "Convert Lead", "Convert this lead to:", choices, 0, False
        )
        if not ok:
            return

        lead = self._lead
        updated_lead = None

        if choice == "item":
            from modules.intel.models.intel_items import IntelItem
            _VALID_PRIORITIES = {"Critical", "High", "Medium", "Low"}
            notes_parts = [p for p in (lead.summary, lead.notes) if p]
            item = IntelItem(
                id="",
                incident_id=lead.incident_id,
                item_type="Other",
                title=lead.title,
                priority=lead.priority if lead.priority in _VALID_PRIORITIES else "Medium",
                notes="\n\n".join(notes_parts) or None,
                location_text=lead.location_text,
                source_lead_id=lead.id,
                linked_subject_ids=[lead.source_subject_id] if lead.source_subject_id else [],
            )
            updated_lead, _ = self._service.convert_lead_to_item(lead, item)

        elif choice == "subject":
            from modules.intel.models.subjects import Subject, SubjectType
            subject = Subject(
                id="",
                incident_id=lead.incident_id,
                subject_type=SubjectType.CONTACT,
                name=lead.title,
                notes=lead.summary,
            )
            updated_lead, _ = self._service.convert_lead_to_subject(lead, subject)

        elif choice == "assessment":
            from modules.intel.models.assessments import Assessment
            assessment = Assessment(
                id="",
                incident_id=lead.incident_id,
                title=lead.title,
                summary=lead.summary,
            )
            updated_lead, _ = self._service.convert_lead_to_assessment(lead, assessment)

        if updated_lead:
            self._lead = updated_lead
            self.lead_updated.emit(updated_lead)
            self._refresh_body()
        else:
            QMessageBox.warning(
                self,
                "Conversion Failed",
                f"Could not convert this lead to {choice}.\n"
                "The lead has not been marked as converted.",
            )

    def _close_lead(self) -> None:
        self._service.leads.close(self._lead.id)
        self.lead_updated.emit(self._lead)
        self.close()

    def _reject(self) -> None:
        updated = self._service.leads.update(self._lead.id, {"status": LeadStatus.REJECTED})
        if updated:
            self._lead = updated
            self.lead_updated.emit(updated)
            self.close()
