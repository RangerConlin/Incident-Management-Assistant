"""API-backed access layer for planning objective templates (MongoDB via SARApp server)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


PRIORITY_VALUES = ("Low", "Normal", "High", "Urgent")

_BASE = "/api/master/objective-templates"


def _client():
    from utils.api_client import api_client
    return api_client


@dataclass(slots=True)
class ObjectiveTemplate:
    """Mirrors the objective_templates schema."""

    id: Optional[int] = None
    code: Optional[str] = None
    title: str = ""
    description: str = ""
    default_section: Optional[str] = None
    priority: str = "Normal"
    active: bool = True
    created_at: str = ""
    updated_at: str = ""
    tags: List[str] = field(default_factory=list)


def _doc_to_template(doc: dict) -> ObjectiveTemplate:
    return ObjectiveTemplate(
        id=doc.get("int_id"),
        code=doc.get("code"),
        title=doc.get("title") or "",
        description=doc.get("description") or "",
        default_section=doc.get("default_section"),
        priority=doc.get("priority") or "Normal",
        active=bool(doc.get("active", True)),
        created_at=doc.get("created_at") or "",
        updated_at=doc.get("updated_at") or "",
        tags=list(doc.get("tags") or []),
    )


class ObjectivesDAO:
    """API-backed DAO for objective templates. db_path accepted but ignored."""

    def __init__(self, db_path=None) -> None:
        pass

    def ensure_schema(self) -> None:
        pass

    def list_templates(
        self,
        search: Optional[str] = None,
        include_archived: bool = False,
        tag_filter: Optional[List[str]] = None,
    ) -> List[ObjectiveTemplate]:
        params: dict = {"include_archived": include_archived}
        if search:
            params["search"] = search
        if tag_filter:
            params["tag"] = tag_filter[0] if len(tag_filter) == 1 else ",".join(tag_filter)
        try:
            docs = _client().get(_BASE, params=params)
            return [_doc_to_template(d) for d in (docs or [])]
        except Exception:
            return []

    def get_template(self, template_id: int) -> Optional[ObjectiveTemplate]:
        try:
            doc = _client().get(f"{_BASE}/{template_id}")
            return _doc_to_template(doc) if doc else None
        except Exception:
            return None

    def create_template(self, template: ObjectiveTemplate) -> int:
        payload = {
            "code": template.code,
            "title": template.title,
            "description": template.description,
            "default_section": template.default_section,
            "priority": template.priority,
            "active": template.active,
            "tags": list(template.tags or []),
        }
        doc = _client().post(_BASE, json=payload)
        return int(doc.get("int_id") or 0)

    def update_template(self, template: ObjectiveTemplate) -> None:
        if template.id is None:
            raise ValueError("Template id is required for update")
        payload = {
            "code": template.code,
            "title": template.title,
            "description": template.description,
            "default_section": template.default_section,
            "priority": template.priority,
            "active": template.active,
            "tags": list(template.tags or []),
        }
        _client().patch(f"{_BASE}/{template.id}", json=payload)

    def set_active(self, template_id: int, active: bool) -> None:
        _client().patch(f"{_BASE}/{template_id}/active", json={"active": active})

    def list_tags(self) -> List[str]:
        try:
            return _client().get(f"{_BASE}/tags") or []
        except Exception:
            return []

    def upsert_tag(self, name: str) -> int:
        return 0

    def replace_template_tags(self, template_id: int, tags) -> None:
        _client().patch(f"{_BASE}/{template_id}", json={"tags": list(tags or [])})

    def delete_template(self, template_id: int) -> None:
        _client().delete(f"{_BASE}/{template_id}")


__all__ = [
    "ObjectiveTemplate",
    "ObjectivesDAO",
    "PRIORITY_VALUES",
]
