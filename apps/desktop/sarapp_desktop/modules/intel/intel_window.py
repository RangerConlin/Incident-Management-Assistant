"""IntelWindow — standalone QMainWindow composing all 8 Intel module tabs.

Opened via open_intel_window() in modules/intel/__init__.py.  Never docked.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QMainWindow, QWidget, QTabWidget, QVBoxLayout
from PySide6.QtCore import Qt

from modules.intel.services.intel_service import IntelService
from modules.intel.tabs.dashboard_tab import DashboardTab
from modules.intel.tabs.subjects_tab import SubjectsTab
from modules.intel.tabs.leads_tab import LeadsTab
from modules.intel.tabs.intel_items_tab import IntelItemsTab
from modules.intel.tabs.assessments_tab import AssessmentsTab
from modules.intel.tabs.log_tab import IntelLogTab
from modules.intel.tabs.forms_tab import FormsTab


_TAB_NAMES = [
    "dashboard",
    "subjects",
    "leads",
    "items",
    "assessments",
    "log",
    "forms",
]


class IntelWindow(QMainWindow):
    """Main Intel module window.

    Contains 8 tabs.  Opened as a modeless standalone window that
    persists independently of the main application window.
    """

    def __init__(
        self,
        incident_id: Optional[str],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._incident_id = incident_id
        self._service = IntelService(incident_id) if incident_id else None
        # service may be None when no active incident — all tabs must guard against this

        self.setWindowTitle("Intel Module")
        self.resize(1100, 720)
        self.setMinimumSize(640, 420)
        self.setAttribute(Qt.WA_DeleteOnClose)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._tabs.setTabPosition(QTabWidget.North)
        self._tabs.setDocumentMode(True)

        self._dashboard_tab = DashboardTab(self._service)
        self._dashboard_tab.navigate_to_tab.connect(self.switch_to_tab)
        self._subjects_tab = SubjectsTab(self._service)
        self._leads_tab = LeadsTab(self._service)
        self._items_tab = IntelItemsTab(self._service)
        self._assessments_tab = AssessmentsTab(self._service)
        self._log_tab = IntelLogTab(self._service)
        self._forms_tab = FormsTab(incident_id=incident_id)

        self._tabs.addTab(self._dashboard_tab, "Dashboard")
        self._tabs.addTab(self._subjects_tab, "Subjects")
        self._tabs.addTab(self._leads_tab, "Leads")
        self._tabs.addTab(self._items_tab, "Intel Items")
        self._tabs.addTab(self._assessments_tab, "Assessments")
        self._tabs.addTab(self._log_tab, "Intel Log")
        self._tabs.addTab(self._forms_tab, "Forms")

        root.addWidget(self._tabs)

        # Wire cross-tab signals
        self._wire_signals()

    def _wire_signals(self) -> None:
        """Connect cross-tab navigation signals."""
        # Opening detail windows from subjects tab
        if hasattr(self._subjects_tab, "open_subject_detail"):
            self._subjects_tab.open_subject_detail.connect(self._open_subject_detail)

        # Opening detail windows from leads tab
        if hasattr(self._leads_tab, "open_lead_detail"):
            self._leads_tab.open_lead_detail.connect(self._open_lead_detail)
        if hasattr(self._leads_tab, "convert_lead"):
            self._leads_tab.convert_lead.connect(self._on_convert_lead)

        # Opening detail windows from items tab
        if hasattr(self._items_tab, "open_item_detail"):
            self._items_tab.open_item_detail.connect(self._open_item_detail)

        # Opening detail windows from assessments tab
        if hasattr(self._assessments_tab, "open_assessment_detail"):
            self._assessments_tab.open_assessment_detail.connect(
                self._open_assessment_detail
            )

        # Log tab navigation
        if hasattr(self._log_tab, "navigate_to_record"):
            self._log_tab.navigate_to_record.connect(self._open_record_from_log)

    def load_incident(self, incident_id: Optional[str]) -> None:
        """Swap in a new incident without closing the window."""
        self._incident_id = incident_id
        self._service = IntelService(incident_id) if incident_id else None
        for tab in (
            self._dashboard_tab, self._subjects_tab, self._leads_tab,
            self._items_tab, self._assessments_tab, self._log_tab,
        ):
            tab._service = self._service
            tab.refresh()
        self._forms_tab._incident_id = incident_id
        title = f"Intel Module — {incident_id}" if incident_id else "Intel Module"
        self.setWindowTitle(title)

    def switch_to_tab(self, tab_name: str) -> None:
        """Switch to the named tab. Silently ignores unknown names."""
        if tab_name in _TAB_NAMES:
            self._tabs.setCurrentIndex(_TAB_NAMES.index(tab_name))

    # ------------------------------------------------------------------
    # Detail window openers

    def _open_subject_detail(self, subject) -> None:
        from modules.intel.windows.subject_detail_window import SubjectDetailWindow
        win = SubjectDetailWindow(subject, self._service, parent=self)
        win.subject_updated.connect(self._subjects_tab.refresh)
        win.show()
        win.raise_()

    def _open_lead_detail(self, lead) -> None:
        from modules.intel.windows.lead_detail_window import LeadDetailWindow
        win = LeadDetailWindow(lead, self._service, parent=self)
        win.lead_updated.connect(self._leads_tab.refresh)
        win.show()
        win.raise_()

    def _open_item_detail(self, item) -> None:
        from modules.intel.windows.intel_item_detail_window import IntelItemDetailWindow
        win = IntelItemDetailWindow(item, self._service, parent=self)
        win.item_updated.connect(self._items_tab.refresh)
        win.show()
        win.raise_()

    def _open_assessment_detail(self, assessment) -> None:
        from modules.intel.windows.assessment_detail_window import AssessmentDetailWindow
        win = AssessmentDetailWindow(assessment, self._service, parent=self)
        win.assessment_updated.connect(self._assessments_tab.refresh)
        win.show()
        win.raise_()

    def _open_record_from_log(self, entity_type: str, entity_id: str) -> None:
        """Open the detail window for a record referenced by a log entry."""
        if not self._service:
            return
        try:
            if entity_type == "lead":
                record = self._service.leads.get(entity_id)
                if record:
                    self._open_lead_detail(record)
            elif entity_type in ("item", "observation"):
                # observation entity_id is the parent item's id
                record = self._service.items.get(entity_id)
                if record:
                    self._open_item_detail(record)
            elif entity_type == "subject":
                record = self._service.subjects.get(entity_id)
                if record:
                    self._open_subject_detail(record)
            elif entity_type == "assessment":
                record = self._service.assessments.get(entity_id)
                if record:
                    self._open_assessment_detail(record)
        except Exception:
            pass  # silently skip if record no longer exists

    def _on_convert_lead(self, lead) -> None:
        """Create an Intel Item from the lead and mark the lead as converted."""
        if not self._service:
            return
        from PySide6.QtWidgets import QMessageBox
        from modules.intel.models.intel_items import IntelItem

        _VALID_PRIORITIES = {"Critical", "High", "Medium", "Low"}
        notes_parts = [p for p in (lead.summary, lead.notes) if p]
        item = IntelItem(
            id="",
            incident_id=self._incident_id,
            item_type="Other",
            title=lead.title,
            priority=lead.priority if lead.priority in _VALID_PRIORITIES else "Medium",
            notes="\n\n".join(notes_parts) or None,
            location_text=lead.location_text,
            source_lead_id=lead.id,
            linked_subject_ids=[lead.source_subject_id] if lead.source_subject_id else [],
        )
        updated_lead, created_item = self._service.convert_lead_to_item(lead, item)
        if created_item:
            self._leads_tab.refresh()
            self._items_tab.refresh()
            self._log_tab.refresh()
        else:
            QMessageBox.warning(
                self,
                "Conversion Failed",
                "Could not create an Intel Item from this lead.\n"
                "The lead has not been marked as converted.",
            )
