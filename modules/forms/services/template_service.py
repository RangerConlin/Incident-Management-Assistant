from __future__ import annotations

from typing import Any

from modules.forms.models import FormFamily, FormFieldDefinition, FormTemplate, FormTemplateVersion
from modules.forms.repositories import MasterFormsRepository
from modules.forms.repositories.master_forms_repository import ApiMasterFormsRepository


class TemplateService:
    def __init__(self, repository=None) -> None:
        self.repository = repository or ApiMasterFormsRepository()

    def create_family(self, *, code: str, title: str, description: str | None = None, category: str | None = None, default_agency: str | None = None) -> FormFamily:
        return self.repository.create_family(FormFamily(code=code, title=title, description=description, category=category, default_agency=default_agency))

    def list_families(self, **filters: Any) -> list[dict[str, Any]]:
        return self.repository.list_families(**filters)

    def create_template(self, *, family_id: int | None = None, family_code: str | None = None, agency: str, code: str, title: str, fields: list[dict[str, Any]], layout: dict[str, Any] | None = None, system: str | None = None, description: str | None = None, created_by: str | None = None, **extra: Any) -> dict[str, Any]:
        if family_id is None:
            if not family_code:
                raise ValueError("family_id or family_code is required")
            family = self.repository.get_family_by_code(family_code)
            if not family:
                raise ValueError("form family not found")
            family_id = int(family["id"])
        template = self.repository.create_template(FormTemplate(family_id=family_id, agency=agency, system=system, code=code, title=title, description=description, created_by=created_by, compatibility=extra.get("compatibility", {}), tags=extra.get("tags", []), status=extra.get("status", "active")))
        version = self.create_version(template.id or 0, fields=fields, layout=layout or {}, created_by=created_by, change_summary="initial version", **extra)
        result = self.repository.get_template(template.id or 0) or {}
        result["current_version"] = version
        return result

    def create_version(self, template_id: int, *, fields: list[dict[str, Any]], layout: dict[str, Any] | None = None, created_by: str | None = None, change_summary: str | None = None, **extra: Any) -> dict[str, Any]:
        versions = self.repository.list_template_versions(template_id)
        next_number = (max([int(v["version_number"]) for v in versions]) + 1) if versions else 1
        field_models = [FormFieldDefinition(**f) for f in fields]
        version = FormTemplateVersion(template_id=template_id, version_number=next_number, layout=layout or {}, fields=field_models, version_label=extra.get("version_label"), effective_date=extra.get("effective_date"), retired_date=extra.get("retired_date"), export_profiles=extra.get("export_profiles", {}), source_asset_path=extra.get("source_asset_path"), checksum=extra.get("checksum"), change_summary=change_summary, created_by=created_by)
        saved = self.repository.create_template_version(version)
        return self.repository.get_template_version(template_id, saved.id or 0) or {}

    def list_templates(self, **filters: Any) -> list[dict[str, Any]]:
        return self.repository.list_templates(**filters)

    def get_template(self, template_id: int) -> dict[str, Any] | None:
        return self.repository.get_template(template_id)

    def list_versions(self, template_id: int) -> list[dict[str, Any]]:
        return self.repository.list_template_versions(template_id)

    def get_version(self, template_id: int, version_id: int) -> dict[str, Any] | None:
        return self.repository.get_template_version(template_id, version_id)

    def retire_template(self, template_id: int, user_id: str | None = None) -> None:
        self.repository.retire_template(template_id, user_id)
