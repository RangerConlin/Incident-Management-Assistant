from __future__ import annotations

from modules.forms.repositories.incident_forms_repository import ApiIncidentFormsRepository


class AuditService:
    def __init__(self, incident_repository: ApiIncidentFormsRepository) -> None:
        self.incident_repository = incident_repository

    def list_instance_audit(self, instance_id: int) -> list[dict]:
        return self.incident_repository.list_audit(instance_id)

    def list_instance_revisions(self, instance_id: int) -> list[dict]:
        return self.incident_repository.list_revisions(instance_id)
