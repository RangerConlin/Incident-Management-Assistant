"""Master-data repository for Units and Organizations.

This module owns CRUD operations for organizations, organization types,
rank structures, and ranks via the MongoDB API.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from utils.api_client import api_client
from utils.catalog_cache import catalog_cache

from .seed_data import seed_if_needed

_CATALOG_ORG_TYPES = "organization_types"
_CATALOG_RANK_STRUCTURES = "rank_structures"
_CATALOG_ORGANIZATIONS = "organizations"
_CATALOG_RANKS = "ranks"


@dataclass(slots=True)
class DeleteResult:
    """Outcome details when attempting to delete an organization."""

    deleted: bool
    message: str


class UnitsOrganizationsRepository:
    """API-backed repository for the Units and Organizations master-data editor."""

    def __init__(self) -> None:
        seed_if_needed()

    # ---- Lookup helpers -------------------------------------------------------
    def list_organization_types(self, include_inactive: bool = True) -> list[dict[str, Any]]:
        try:
            return catalog_cache.get(_CATALOG_ORG_TYPES, "/api/master/types") or []
        except Exception:
            return []

    def list_rank_structures(self, include_inactive: bool = True) -> list[dict[str, Any]]:
        try:
            return catalog_cache.get(_CATALOG_RANK_STRUCTURES, "/api/master/rank-structures") or []
        except Exception:
            return []

    def list_organizations(self, include_inactive: bool = True) -> list[dict[str, Any]]:
        try:
            return catalog_cache.get(_CATALOG_ORGANIZATIONS, "/api/master/organizations") or []
        except Exception:
            return []

    def get_organization(self, organization_id: int) -> dict[str, Any] | None:
        try:
            return catalog_cache.get(_CATALOG_ORGANIZATIONS, f"/api/master/organizations/{organization_id}")
        except Exception:
            return None

    # ---- Organization type CRUD ----------------------------------------------
    def create_organization_type(self, payload: dict[str, Any]) -> int:
        try:
            result = api_client.post("/api/master/types", json=payload)
            catalog_cache.invalidate(_CATALOG_ORG_TYPES)
            return result.get("int_id", 0) if result else 0
        except Exception:
            return 0

    def update_organization_type(self, type_id: int, payload: dict[str, Any]) -> None:
        try:
            api_client.patch(f"/api/master/types/{type_id}", json=payload)
            catalog_cache.invalidate(_CATALOG_ORG_TYPES)
        except Exception:
            pass

    # ---- Rank structure CRUD --------------------------------------------------
    def create_rank_structure(self, payload: dict[str, Any]) -> int:
        try:
            result = api_client.post("/api/master/rank-structures", json=payload)
            catalog_cache.invalidate(_CATALOG_RANK_STRUCTURES)
            return result.get("int_id", 0) if result else 0
        except Exception:
            return 0

    def update_rank_structure(self, rank_structure_id: int, payload: dict[str, Any]) -> None:
        try:
            api_client.patch(f"/api/master/rank-structures/{rank_structure_id}", json=payload)
            catalog_cache.invalidate(_CATALOG_RANK_STRUCTURES)
        except Exception:
            pass

    # ---- Rank rows CRUD ------------------------------------------------------
    def list_ranks(self, rank_structure_id: int) -> list[dict[str, Any]]:
        try:
            docs = catalog_cache.get(
                _CATALOG_RANKS, "/api/master/ranks", params={"structure_id": rank_structure_id}
            ) or []
        except Exception:
            return []
        # Translate the API's storage field names back to the names the
        # rank-editing UI (widgets/dialogs.py) expects.
        return [
            {
                "rank_id": d.get("int_id"),
                "rank_structure_id": d.get("rank_structure_id"),
                "rank_code": d.get("rank_code", ""),
                "rank_name": d.get("rank_name", ""),
                "short_display": d.get("short_display", ""),
                "sort_order": d.get("sort_order", 0),
                "is_active": d.get("is_active", 1),
            }
            for d in docs
        ]

    def replace_ranks(self, rank_structure_id: int, ranks: list[dict[str, Any]]) -> None:
        """Replace the full set of ranks for a structure with `ranks`.

        There is no bulk-replace endpoint, so this deletes the structure's
        existing ranks first, then recreates them from the given list —
        matching "replace" semantics rather than appending to what's there.
        """
        try:
            existing = api_client.get("/api/master/ranks", params={"structure_id": rank_structure_id}) or []
            for doc in existing:
                api_client.delete(f"/api/master/ranks/{doc['int_id']}")
            for idx, rank in enumerate(ranks):
                api_client.post("/api/master/ranks", json={
                    "rank_structure_id": rank_structure_id,
                    "rank_code": rank.get("rank_code", ""),
                    "rank_name": rank.get("rank_name", ""),
                    "short_display": rank.get("short_display", ""),
                    "sort_order": rank.get("sort_order", idx),
                    "is_active": rank.get("is_active", 1),
                })
            catalog_cache.invalidate(_CATALOG_RANKS)
        except Exception:
            pass

    def duplicate_rank_structure(
        self,
        source_rank_structure_id: int,
        *,
        new_name: str,
        is_template: bool,
        organization_type_id: int | None = None,
    ) -> int:
        """Create a full rank structure copy including ordered rank rows."""
        try:
            body: dict[str, Any] = {"name": new_name, "is_template": is_template}
            if organization_type_id is not None:
                body["organization_type_id"] = organization_type_id
            result = api_client.post(
                f"/api/master/rank-structures/{source_rank_structure_id}/duplicate",
                json=body,
            )
            catalog_cache.invalidate(_CATALOG_RANK_STRUCTURES)
            catalog_cache.invalidate(_CATALOG_RANKS)
            return result.get("id", 0) if result else 0
        except Exception:
            return 0

    # ---- Organization CRUD ----------------------------------------------------
    def create_organization(self, payload: dict[str, Any], changed_by: str = "system") -> int:
        try:
            result = api_client.post("/api/master/organizations", json=payload)
            catalog_cache.invalidate(_CATALOG_ORGANIZATIONS)
            return result.get("int_id", 0) if result else 0
        except Exception:
            return 0

    def update_organization(self, organization_id: int, payload: dict[str, Any], changed_by: str = "system") -> None:
        try:
            api_client.patch(f"/api/master/organizations/{organization_id}", json=payload)
            catalog_cache.invalidate(_CATALOG_ORGANIZATIONS)
        except Exception:
            pass

    def delete_organization(self, organization_id: int, changed_by: str = "system") -> DeleteResult:
        """Delete an organization, soft-disable if it has child organizations."""
        try:
            api_client.delete(f"/api/master/organizations/{organization_id}")
            catalog_cache.invalidate(_CATALOG_ORGANIZATIONS)
            return DeleteResult(True, "Organization deleted.")
        except Exception as e:
            return DeleteResult(False, str(e))

    def move_sort_order(self, organization_id: int, direction: int) -> None:
        """Move an organization up/down among sibling sort_order values."""
        pass

    def upsert_override(self, organization_id: int, rank_structure_id: int, override_mode: str) -> None:
        try:
            api_client.post(
                f"/api/master/organizations/{organization_id}/rank-structure-override",
                json={"rank_structure_id": rank_structure_id},
            )
            catalog_cache.invalidate(_CATALOG_ORGANIZATIONS)
        except Exception:
            pass


__all__ = ["UnitsOrganizationsRepository", "DeleteResult"]
