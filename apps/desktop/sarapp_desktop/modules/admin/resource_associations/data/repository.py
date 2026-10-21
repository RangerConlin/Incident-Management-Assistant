"""API-backed repository for Resource Associations (Stage 2)."""
from __future__ import annotations

from typing import Any

from ..models import ResourceAssociation, ResourceEndpoint


def _doc_to_model(doc: dict[str, Any]) -> ResourceAssociation:
    src = doc.get("source") or {}
    dst = doc.get("target") or {}
    return ResourceAssociation(
        id=doc.get("id") or doc.get("_id"),
        source=ResourceEndpoint(
            resource_type=src.get("resource_type", ""),
            resource_id=int(src.get("resource_id") or 0),
            label=doc.get("source_label", ""),
        ),
        target=ResourceEndpoint(
            resource_type=dst.get("resource_type", ""),
            resource_id=int(dst.get("resource_id") or 0),
            label=doc.get("target_label", ""),
        ),
        association_type=doc.get("association_type", "Associated"),
        owning_organization=doc.get("owning_organization"),
        effective_start=doc.get("effective_start"),
        effective_end=doc.get("effective_end"),
        notes=doc.get("notes", ""),
        active=bool(doc.get("active", True)),
        created_at=doc.get("created_at", ""),
        updated_at=doc.get("updated_at", ""),
    )


class ApiResourceAssociationRepository:
    """Drop-in repository that calls the resource-associations API."""

    def list_for_resource(
        self, resource_type: str, resource_id: int, *, role: str = "either", include_inactive: bool = True
    ) -> list[ResourceAssociation]:
        from utils.api_client import api_client

        docs = api_client.get(
            "/api/resource-associations",
            params={
                "resource_type": resource_type,
                "resource_id": resource_id,
                "role": role,
                "include_inactive": include_inactive,
            },
        ) or []
        return [_doc_to_model(d) for d in docs]

    def create(self, association: ResourceAssociation, *, created_by: str = "") -> ResourceAssociation:
        from utils.api_client import api_client

        payload = {
            "source": {
                "resource_type": association.source.resource_type,
                "resource_id": association.source.resource_id,
            },
            "target": {
                "resource_type": association.target.resource_type,
                "resource_id": association.target.resource_id,
            },
            "association_type": association.association_type,
            "owning_organization": association.owning_organization,
            "effective_start": association.effective_start,
            "effective_end": association.effective_end,
            "notes": association.notes,
            "active": association.active,
            "created_by": created_by,
        }
        doc = api_client.post("/api/resource-associations", json=payload)
        return _doc_to_model(doc)

    def update(self, association_id: str, **fields: Any) -> ResourceAssociation:
        from utils.api_client import api_client

        doc = api_client.patch(f"/api/resource-associations/{association_id}", json=fields)
        return _doc_to_model(doc)

    def delete(self, association_id: str) -> None:
        from utils.api_client import api_client

        api_client.delete(f"/api/resource-associations/{association_id}")

    def suggested_types(self) -> list[str]:
        from utils.api_client import api_client

        try:
            return api_client.get("/api/resource-associations/types/suggested") or []
        except Exception:
            from ..models import SUGGESTED_ASSOCIATION_TYPES

            return list(SUGGESTED_ASSOCIATION_TYPES)
