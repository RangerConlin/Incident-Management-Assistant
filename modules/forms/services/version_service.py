from __future__ import annotations

from .template_service import TemplateService


class VersionService:
    def __init__(self, template_service: TemplateService | None = None) -> None:
        self.template_service = template_service or TemplateService()

    def list_template_versions(self, template_id: int) -> list[dict]:
        return self.template_service.list_versions(template_id)

    def create_template_version(self, template_id: int, **payload) -> dict:
        return self.template_service.create_version(template_id, **payload)
