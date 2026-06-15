"""IntelService — central facade for all Intel module data operations.

Tabs and detail windows should import IntelService rather than repositories
directly.  This provides a single place to add caching, validation, or
cross-entity business logic in the future.
"""

from __future__ import annotations

from typing import Optional

from utils.api_client import api_client, APIError

from modules.intel.models.subjects import Subject
from modules.intel.models.leads import Lead
from modules.intel.models.intel_items import IntelItem, Observation
from modules.intel.models.assessments import Assessment
from modules.intel.models.log_entry import IntelLogEntry

from modules.intel.repositories.subjects_repo import SubjectsRepository
from modules.intel.repositories.leads_repo import LeadsRepository
from modules.intel.repositories.intel_items_repo import IntelItemsRepository
from modules.intel.repositories.assessments_repo import AssessmentsRepository
from modules.intel.repositories.log_repo import IntelLogRepository


class IntelService:
    """All-in-one access point for the Intel module's data layer."""

    def __init__(self, incident_id: str) -> None:
        self.incident_id = incident_id
        self.subjects = SubjectsRepository(incident_id)
        self.leads = LeadsRepository(incident_id)
        self.items = IntelItemsRepository(incident_id)
        self.assessments = AssessmentsRepository(incident_id)
        self.log = IntelLogRepository(incident_id)

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def get_dashboard(self) -> dict:
        """Return summary counts and recent activity for the dashboard tab."""
        try:
            return api_client.get(
                f"/api/incidents/{self.incident_id}/intel/dashboard"
            )
        except APIError:
            return {
                "active_subjects": 0,
                "open_leads": 0,
                "total_items": 0,
                "critical_items": 0,
                "worsening_items": 0,
                "improving_items": 0,
                "open_assessments": 0,
                "recent_activity": [],
            }

    # ------------------------------------------------------------------
    # Lead conversion
    # ------------------------------------------------------------------

    def convert_lead_to_subject(
        self, lead: Lead, subject: Subject, actor: str = "system"
    ) -> tuple[Optional[Lead], Optional[Subject]]:
        """Convert a lead into a new Subject, preserving the relationship."""
        created = self.subjects.create(subject)
        if created:
            updated_lead = self.leads.convert(lead.id, "subject", actor=actor)
            return updated_lead, created
        return None, None

    def convert_lead_to_item(
        self, lead: Lead, item: IntelItem, actor: str = "system"
    ) -> tuple[Optional[Lead], Optional[IntelItem]]:
        """Convert a lead into a new IntelItem, preserving the relationship."""
        item.source_lead_id = lead.id
        created = self.items.create(item)
        if created:
            updated_lead = self.leads.convert(lead.id, "item", actor=actor)
            return updated_lead, created
        return None, None

    def convert_lead_to_assessment(
        self, lead: Lead, assessment: Assessment, actor: str = "system"
    ) -> tuple[Optional[Lead], Optional[Assessment]]:
        """Convert a lead into a new Assessment, preserving the relationship."""
        created = self.assessments.create(assessment)
        if created:
            updated_lead = self.leads.convert(lead.id, "assessment", actor=actor)
            return updated_lead, created
        return None, None
