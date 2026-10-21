"""API-backed repository for Resource Packages (Stage 3)."""
from __future__ import annotations

from typing import Any

from ..models import (
    MinimumQuantityRequirement,
    PackageResourceRef,
    RequiredPosition,
    ResourcePackage,
)


def _doc_to_model(doc: dict[str, Any]) -> ResourcePackage:
    return ResourcePackage(
        id=doc.get("id") or doc.get("_id"),
        name=doc.get("name", ""),
        description=doc.get("description", ""),
        owning_organization=doc.get("owning_organization", ""),
        parent_org_unit=doc.get("parent_org_unit"),
        linked_resource_type_id=doc.get("linked_resource_type_id"),
        default_team_designation=doc.get("default_team_designation", ""),
        resources=[
            PackageResourceRef(
                resource_type=r.get("resource_type", ""),
                resource_id=int(r.get("resource_id") or 0),
                membership=r.get("membership", "fixed"),
                role=r.get("role", ""),
                label=r.get("label", ""),
            )
            for r in (doc.get("resources") or [])
        ],
        required_positions=[
            RequiredPosition(
                role=p.get("role", ""),
                qualification=p.get("qualification", ""),
                quantity=int(p.get("quantity") or 1),
                notes=p.get("notes", ""),
            )
            for p in (doc.get("required_positions") or [])
        ],
        minimum_quantities=[
            MinimumQuantityRequirement(
                description=m.get("description", ""),
                resource_kind=m.get("resource_kind", ""),
                qualification=m.get("qualification", ""),
                minimum_count=int(m.get("minimum_count") or 1),
            )
            for m in (doc.get("minimum_quantities") or [])
        ],
        is_active=bool(doc.get("is_active", True)),
        notes=doc.get("notes", ""),
        created_at=doc.get("created_at", ""),
        updated_at=doc.get("updated_at", ""),
        personnel_count=int(doc.get("personnel_count") or 0),
        vehicle_count=int(doc.get("vehicle_count") or 0),
        aircraft_count=int(doc.get("aircraft_count") or 0),
        equipment_count=int(doc.get("equipment_count") or 0),
        asset_count=int(doc.get("asset_count") or 0),
    )


def _model_to_payload(package: ResourcePackage, *, created_by: str = "") -> dict[str, Any]:
    return {
        "name": package.name,
        "description": package.description,
        "owning_organization": package.owning_organization,
        "parent_org_unit": package.parent_org_unit,
        "linked_resource_type_id": package.linked_resource_type_id,
        "default_team_designation": package.default_team_designation,
        "resources": [
            {
                "resource_type": r.resource_type,
                "resource_id": r.resource_id,
                "membership": r.membership,
                "role": r.role,
            }
            for r in package.resources
        ],
        "required_positions": [
            {
                "role": p.role,
                "qualification": p.qualification,
                "quantity": p.quantity,
                "notes": p.notes,
            }
            for p in package.required_positions
        ],
        "minimum_quantities": [
            {
                "description": m.description,
                "resource_kind": m.resource_kind,
                "qualification": m.qualification,
                "minimum_count": m.minimum_count,
            }
            for m in package.minimum_quantities
        ],
        "is_active": package.is_active,
        "notes": package.notes,
        "created_by": created_by,
    }


class ApiResourcePackageRepository:
    """Drop-in repository that calls the resource-packages API."""

    def list_packages(
        self, *, search: str = "", owning_organization: str = "", active_filter: str = "Active"
    ) -> list[ResourcePackage]:
        from utils.api_client import api_client

        docs = api_client.get(
            "/api/resource-packages",
            params={"search": search, "owning_organization": owning_organization, "active_filter": active_filter},
        ) or []
        return [_doc_to_model(d) for d in docs]

    def get_package(self, package_id: str) -> ResourcePackage | None:
        from utils.api_client import APIError, api_client

        try:
            doc = api_client.get(f"/api/resource-packages/{package_id}")
        except APIError as exc:
            if getattr(exc, "status_code", None) == 404:
                return None
            raise
        return _doc_to_model(doc) if doc else None

    def save_package(self, package: ResourcePackage, *, created_by: str = "") -> ResourcePackage:
        from utils.api_client import api_client

        payload = _model_to_payload(package, created_by=created_by)
        if package.id is None:
            doc = api_client.post("/api/resource-packages", json=payload)
        else:
            doc = api_client.put(f"/api/resource-packages/{package.id}", json=payload)
        return _doc_to_model(doc)

    def duplicate_package(self, package_id: str) -> ResourcePackage:
        from utils.api_client import api_client

        doc = api_client.post(f"/api/resource-packages/{package_id}/duplicate")
        return _doc_to_model(doc)

    def set_active(self, package_id: str, active: bool) -> ResourcePackage:
        from utils.api_client import api_client

        doc = api_client.patch(f"/api/resource-packages/{package_id}/active", json={"active": active})
        return _doc_to_model(doc)

    def packages_for_resource(self, resource_type: str, resource_id: int) -> list[ResourcePackage]:
        from utils.api_client import api_client

        docs = api_client.get(f"/api/resource-packages/for-resource/{resource_type}/{resource_id}") or []
        return [_doc_to_model(d) for d in docs]
