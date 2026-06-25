"""API-backed access layer for master strategy templates (MongoDB via SARApp server).

A strategy template is a suggested ICS-204 work assignment that can be
imported alongside an objective. See objectives_dao.py for the analogous
objective-template DAO.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

PRIORITY_VALUES = ("Low", "Normal", "High", "Urgent")
ASSIGNMENT_KIND_VALUES = ("Ground", "Air", "Marine", "Other")

_BASE = "/api/master/strategy-templates"


def _client():
    from utils.api_client import api_client
    return api_client


@dataclass(slots=True)
class StrategyTemplate:
    """Mirrors the strategy_templates schema."""

    id: Optional[int] = None
    objective_template_id: Optional[int] = None
    title: str = ""
    description: str = ""
    assignment_kind: str = "Ground"
    branch: Optional[str] = None
    division_group: Optional[str] = None
    priority: str = "Normal"
    active: bool = True
    created_at: str = ""
    updated_at: str = ""
    tags: List[str] = field(default_factory=list)


def _doc_to_template(doc: dict) -> StrategyTemplate:
    return StrategyTemplate(
        id=doc.get("int_id"),
        objective_template_id=doc.get("objective_template_id"),
        title=doc.get("title") or "",
        description=doc.get("description") or "",
        assignment_kind=doc.get("assignment_kind") or "Ground",
        branch=doc.get("branch"),
        division_group=doc.get("division_group"),
        priority=doc.get("priority") or "Normal",
        active=bool(doc.get("active", True)),
        created_at=doc.get("created_at") or "",
        updated_at=doc.get("updated_at") or "",
        tags=list(doc.get("tags") or []),
    )


class StrategyTemplatesDAO:
    """API-backed DAO for strategy templates."""

    def list_templates(
        self,
        search: Optional[str] = None,
        include_archived: bool = False,
        objective_template_id: Optional[int] = None,
        tag_filter: Optional[List[str]] = None,
    ) -> List[StrategyTemplate]:
        params: dict = {"include_archived": include_archived}
        if search:
            params["search"] = search
        if objective_template_id is not None:
            params["objective_template_id"] = objective_template_id
        if tag_filter:
            params["tag"] = tag_filter[0] if len(tag_filter) == 1 else ",".join(tag_filter)
        try:
            docs = _client().get(_BASE, params=params)
            return [_doc_to_template(d) for d in (docs or [])]
        except Exception:
            return []

    def get_template(self, template_id: int) -> Optional[StrategyTemplate]:
        try:
            doc = _client().get(f"{_BASE}/{template_id}")
            return _doc_to_template(doc) if doc else None
        except Exception:
            return None

    def create_template(self, template: StrategyTemplate) -> int:
        payload = {
            "objective_template_id": template.objective_template_id,
            "title": template.title,
            "description": template.description,
            "assignment_kind": template.assignment_kind,
            "branch": template.branch,
            "division_group": template.division_group,
            "priority": template.priority,
            "active": template.active,
            "tags": list(template.tags or []),
        }
        doc = _client().post(_BASE, json=payload)
        return int(doc.get("int_id") or 0)

    def update_template(self, template: StrategyTemplate) -> None:
        if template.id is None:
            raise ValueError("Template id is required for update")
        payload = {
            "objective_template_id": template.objective_template_id,
            "title": template.title,
            "description": template.description,
            "assignment_kind": template.assignment_kind,
            "branch": template.branch,
            "division_group": template.division_group,
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

    def delete_template(self, template_id: int) -> None:
        _client().delete(f"{_BASE}/{template_id}")


__all__ = [
    "StrategyTemplate",
    "StrategyTemplatesDAO",
    "PRIORITY_VALUES",
    "ASSIGNMENT_KIND_VALUES",
]
