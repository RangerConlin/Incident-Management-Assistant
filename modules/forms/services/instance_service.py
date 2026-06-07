from __future__ import annotations

from typing import Any

from modules.forms.repositories import IncidentFormsRepository, MasterFormsRepository
from .binding_service import BindingService


class InstanceService:
    def __init__(self, master_repository: MasterFormsRepository | None = None, binding_service: BindingService | None = None, incident_base_dir=None) -> None:
        self.master_repository = master_repository or MasterFormsRepository()
        self.binding_service = binding_service or BindingService()
        self.incident_base_dir = incident_base_dir

    def repository_for(self, incident_id: str) -> IncidentFormsRepository:
        if self.incident_base_dir is not None:
            return IncidentFormsRepository(incident_id, base_dir=self.incident_base_dir)
        return IncidentFormsRepository(incident_id)

    def create_instance(self, *, incident_id: str, template_id: int | None = None, template_version_id: int | None = None, binding_context: dict[str, Any] | None = None, created_by: str | None = None, **data: Any) -> dict[str, Any]:
        if template_version_id:
            template = self.master_repository.get_template(template_id or int(data.get("template_id", 0))) if template_id else None
            if not template:
                for candidate in self.master_repository.list_templates():
                    versions = self.master_repository.list_template_versions(int(candidate["id"]))
                    if any(int(v["id"]) == template_version_id for v in versions):
                        template = candidate
                        template_id = int(candidate["id"])
                        break
            if not template or not template_id:
                raise ValueError("template for version not found")
            version = self.master_repository.get_template_version(template_id, template_version_id)
        else:
            if not template_id:
                raise ValueError("template_id or template_version_id is required")
            template = self.master_repository.get_template(template_id)
            version = self.master_repository.get_current_version(template_id)
        if not template or not version:
            raise ValueError("template version not found")
        repo = self.repository_for(incident_id)
        instance = repo.create_instance({
            "family_id": template["family_id"], "template_id": template_id, "template_version_id": version["id"],
            "incident_id": incident_id, "title": template.get("title"), "agency": template.get("agency"), "created_by": created_by,
            "operational_period_id": data.get("operational_period_id"), "linked_module": data.get("linked_module"),
            "linked_record_id": data.get("linked_record_id"), "metadata": data.get("metadata", {}),
        })
        updates = self.binding_service.refresh_unlocked_fields(version.get("fields", []), {}, binding_context)
        if updates:
            instance = repo.upsert_values(int(instance["id"]), updates, created_by, require_override_reason=False)
        return instance

    def list_instances(self, incident_id: str, **filters: Any) -> list[dict[str, Any]]:
        return self.repository_for(incident_id).list_instances(**filters)

    def get_instance(self, incident_id: str, instance_id: int) -> dict[str, Any] | None:
        return self.repository_for(incident_id).get_instance(instance_id)

    def update_values(self, incident_id: str, instance_id: int, values: dict[str, Any], user_id: str | None = None) -> dict[str, Any]:
        normalized = {k: (v if isinstance(v, dict) else {"value": v, "display_value": str(v) if v is not None else None}) for k, v in values.items()}
        return self.repository_for(incident_id).upsert_values(instance_id, normalized, user_id)

    def refresh(self, incident_id: str, instance_id: int, context: dict[str, Any] | None = None, user_id: str | None = None) -> dict[str, Any]:
        repo = self.repository_for(incident_id)
        instance = repo.get_instance(instance_id)
        if not instance:
            raise ValueError("instance not found")
        version = self.master_repository.get_template_version(int(instance["template_id"]), int(instance["template_version_id"]))
        updates = self.binding_service.refresh_unlocked_fields((version or {}).get("fields", []), instance.get("values", {}), context)
        if not updates:
            return instance
        return repo.upsert_values(instance_id, updates, user_id, require_override_reason=False)

    def finalize(self, incident_id: str, instance_id: int, user_id: str | None = None) -> dict[str, Any]:
        return self.repository_for(incident_id).finalize_instance(instance_id, user_id)

    def reopen(self, incident_id: str, instance_id: int, user_id: str | None = None, reason: str | None = None) -> dict[str, Any]:
        return self.repository_for(incident_id).reopen_instance(instance_id, user_id, reason)

    def list_revisions(self, incident_id: str, instance_id: int) -> list[dict[str, Any]]:
        return self.repository_for(incident_id).list_revisions(instance_id)

    def list_audit(self, incident_id: str, instance_id: int) -> list[dict[str, Any]]:
        return self.repository_for(incident_id).list_audit(instance_id)
