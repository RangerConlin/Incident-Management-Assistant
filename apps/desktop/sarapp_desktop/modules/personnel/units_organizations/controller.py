"""Controller layer for Units and Organizations panel."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from .models.repository import DeleteResult, UnitsOrganizationsRepository


@dataclass(slots=True)
class TreeNode:
    """In-memory tree node for organization hierarchy rendering."""

    organization: dict[str, Any]
    children: list["TreeNode"]


class UnitsOrganizationsController:
    """Coordinates repository operations and view-friendly transforms."""

    def __init__(self, repository: UnitsOrganizationsRepository | None = None) -> None:
        self.repo = repository or UnitsOrganizationsRepository()

    def list_organizations(self, include_inactive: bool = True) -> list[dict[str, Any]]:
        return self.repo.list_organizations(include_inactive=include_inactive)

    def build_tree(self, include_inactive: bool = True) -> list[TreeNode]:
        rows = self.repo.list_organizations(include_inactive=include_inactive)
        by_parent: dict[int | None, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_parent[row.get("parent_organization_id")].append(row)

        def _build(parent_id: int | None) -> list[TreeNode]:
            nodes: list[TreeNode] = []
            for org in by_parent.get(parent_id, []):
                nodes.append(TreeNode(organization=org, children=_build(org["id"])))
            return nodes

        return _build(None)

    def list_children(self, parent_organization_id: int | None) -> list[dict[str, Any]]:
        rows = self.repo.list_organizations(include_inactive=True)
        children = [r for r in rows if r.get("parent_organization_id") == parent_organization_id]
        return sorted(children, key=lambda r: (int(r.get("sort_order", 0)), (r.get("name") or "").lower()))

    def list_organization_types(self, include_inactive: bool = True) -> list[dict[str, Any]]:
        return self.repo.list_organization_types(include_inactive=include_inactive)

    def save_organization_type(self, type_id: int | None, payload: dict[str, Any]) -> int | None:
        if type_id:
            self.repo.update_organization_type(type_id, payload)
            return type_id
        return self.repo.create_organization_type(payload)

    def list_rank_structures(self, include_inactive: bool = True) -> list[dict[str, Any]]:
        return self.repo.list_rank_structures(include_inactive=include_inactive)

    def save_rank_structure(self, rank_structure_id: int | None, payload: dict[str, Any]) -> int | None:
        if rank_structure_id:
            self.repo.update_rank_structure(rank_structure_id, payload)
            return rank_structure_id
        return self.repo.create_rank_structure(payload)

    # --- Rank editing helpers for templates ---------------------------------
    def list_ranks(self, rank_structure_id: int) -> list[dict[str, Any]]:
        return self.repo.list_ranks(rank_structure_id)

    def save_rank_structure_with_ranks(
        self,
        rank_structure_id: int | None,
        payload: dict[str, Any],
        ranks: list[dict[str, object]],
    ) -> int:
        if rank_structure_id is None:
            # The rank-structures API has no concept of an embedded "ranks"
            # field — it must be created first, then ranks attached via the
            # ranks endpoint, same as the update path below.
            new_id = int(self.repo.create_rank_structure(payload))
            self.repo.replace_ranks(new_id, ranks)
            return new_id
        self.repo.update_rank_structure(rank_structure_id, payload)
        self.repo.replace_ranks(rank_structure_id, ranks)
        return int(rank_structure_id)

    def duplicate_rank_template(
        self,
        source_rank_structure_id: int,
        new_name: str,
        *,
        as_template: bool = True,
        organization_type_id: int | None = None,
    ) -> int:
        return self.repo.duplicate_rank_structure(
            source_rank_structure_id,
            new_name=new_name,
            is_template=as_template,
            organization_type_id=organization_type_id,
        )

    def convert_template_to_custom_copy(self, source_rank_structure_id: int, custom_name: str) -> int:
        return self.repo.duplicate_rank_structure(
            source_rank_structure_id,
            new_name=custom_name,
            is_template=False,
            organization_type_id=None,
        )

    def get_organization(self, organization_id: int) -> dict[str, Any] | None:
        return self.repo.get_organization(organization_id)

    def create_organization(self, payload: dict[str, Any]) -> int:
        return self.repo.create_organization(payload)

    def update_organization(self, organization_id: int, payload: dict[str, Any]) -> None:
        self.repo.update_organization(organization_id, payload)

    def delete_organization(self, organization_id: int) -> DeleteResult:
        return self.repo.delete_organization(organization_id)

    def move_organization(self, organization_id: int, direction: int) -> None:
        self.repo.move_sort_order(organization_id, direction)

    def save_override(self, organization_id: int, rank_structure_id: int, override_mode: str = "replace") -> None:
        self.repo.upsert_override(organization_id, rank_structure_id, override_mode)


__all__ = ["UnitsOrganizationsController", "TreeNode"]
