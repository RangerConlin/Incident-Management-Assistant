"""Resource Packages API router (Stage 3).

A Resource Package is a reusable collection of personnel/vehicles/aircraft/
equipment that routinely respond together (a CAP ground team, a fire engine
company, an ambulance, a patrol unit) -- a standing roster definition, never
an incident team. Membership supports, in combination: fixed resources
(specific ids), preferred resources (normally assigned but substitutable),
optional resources, required positions (role/qualification with no specific
person named), and minimum-quantity requirements. A package must always be
saveable while incomplete/understaffed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.repository import BaseRepository
from sarapp_db.mongo.resource_kinds import RESOURCE_KINDS, find_resource, is_known_resource_type

router = APIRouter()

# Membership kinds a resource reference can carry within a package. A
# resource may legitimately be in multiple packages' standing membership --
# that alone is never a conflict (see Stage 6 conflict-prevention rules).
MEMBERSHIP_KINDS: tuple[str, ...] = ("fixed", "preferred", "optional")


class ResourcePackagesRepository(BaseRepository):
    collection_name = MasterCollections.RESOURCE_PACKAGES


def _repo() -> ResourcePackagesRepository:
    return ResourcePackagesRepository(get_master_db())


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class PackageResourceRef(BaseModel):
    resource_type: str
    resource_id: int
    membership: str = "fixed"
    role: str = ""


class RequiredPosition(BaseModel):
    role: str
    qualification: str = ""
    quantity: int = 1
    notes: str = ""


class MinimumQuantityRequirement(BaseModel):
    description: str
    resource_kind: str = ""
    qualification: str = ""
    minimum_count: int = 1


class SavePackageRequest(BaseModel):
    name: str
    description: str = ""
    owning_organization: str = ""
    parent_org_unit: Optional[str] = None
    linked_resource_type_id: Optional[int] = None
    default_team_designation: str = ""
    resources: list[PackageResourceRef] = []
    required_positions: list[RequiredPosition] = []
    minimum_quantities: list[MinimumQuantityRequirement] = []
    is_active: bool = True
    notes: str = ""
    created_by: str = ""


def _counts(resources: list[dict[str, Any]]) -> dict[str, int]:
    counts = {kind: 0 for kind in RESOURCE_KINDS}
    for ref in resources:
        kind = ref.get("resource_type")
        if kind in counts:
            counts[kind] += 1
    return counts


def _normalize(doc: dict[str, Any]) -> dict[str, Any]:
    d = dict(doc)
    d["id"] = d.pop("_id", None)
    resources = d.get("resources") or []
    counts = _counts(resources)
    d["personnel_count"] = counts.get("personnel", 0)
    d["vehicle_count"] = counts.get("vehicle", 0)
    d["aircraft_count"] = counts.get("aircraft", 0)
    d["equipment_count"] = counts.get("equipment", 0)
    # "vehicle/asset count" for the list view = every non-personnel resource.
    d["asset_count"] = sum(v for k, v in counts.items() if k != "personnel")
    return d


def _validate_resources(db, resources: list[PackageResourceRef]) -> None:
    seen: set[tuple[str, int]] = set()
    for ref in resources:
        if not is_known_resource_type(ref.resource_type):
            raise HTTPException(status_code=400, detail=f"Unknown resource_type: {ref.resource_type!r}")
        if ref.membership not in MEMBERSHIP_KINDS:
            raise HTTPException(status_code=400, detail=f"Unknown membership kind: {ref.membership!r}")
        if find_resource(db, ref.resource_type, ref.resource_id) is None:
            raise HTTPException(
                status_code=404,
                detail=f"Resource {ref.resource_type}:{ref.resource_id} does not exist.",
            )
        key = (ref.resource_type, ref.resource_id)
        if key in seen:
            raise HTTPException(
                status_code=409,
                detail=f"Resource {ref.resource_type}:{ref.resource_id} is listed more than once.",
            )
        seen.add(key)


@router.get("")
def list_packages(
    search: str = Query(""),
    owning_organization: str = Query(""),
    active_filter: str = Query("Active"),
) -> list[dict[str, Any]]:
    repo = _repo()
    query: dict[str, Any] = {}
    if active_filter == "Active":
        query["is_active"] = True
    elif active_filter == "Inactive":
        query["is_active"] = False
    if owning_organization:
        query["owning_organization"] = owning_organization
    docs = repo.find_many(query, sort=[("name", 1)])
    if search.strip():
        t = search.strip().lower()
        docs = [
            d for d in docs
            if t in (d.get("name") or "").lower()
            or t in (d.get("description") or "").lower()
            or t in (d.get("owning_organization") or "").lower()
            or t in (d.get("default_team_designation") or "").lower()
        ]
    return [_normalize(d) for d in docs]


@router.get("/{package_id}")
def get_package(package_id: str) -> dict[str, Any]:
    doc = _repo().find_by_id(package_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Resource package not found")
    return _normalize(doc)


@router.post("", status_code=201)
def create_package(body: SavePackageRequest) -> dict[str, Any]:
    repo = _repo()
    _validate_resources(repo._db, body.resources)
    doc = body.model_dump()
    saved = repo.insert_one(doc)
    return _normalize(saved)


@router.put("/{package_id}")
def save_package(package_id: str, body: SavePackageRequest) -> dict[str, Any]:
    repo = _repo()
    existing = repo.find_by_id(package_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Resource package not found")
    _validate_resources(repo._db, body.resources)
    updates = body.model_dump(exclude={"created_by"})
    repo.update_one(package_id, updates)
    doc = repo.find_by_id(package_id)
    return _normalize(doc)


@router.post("/{package_id}/duplicate", status_code=201)
def duplicate_package(package_id: str) -> dict[str, Any]:
    repo = _repo()
    original = repo.find_by_id(package_id)
    if original is None:
        raise HTTPException(status_code=404, detail="Resource package not found")
    clone = dict(original)
    clone.pop("_id", None)
    base_name = original.get("name", "Package")
    copy_num = 1
    while repo.find_one({"name": f"{base_name} Copy {copy_num}"}):
        copy_num += 1
    clone["name"] = f"{base_name} Copy {copy_num}"
    saved = repo.insert_one(clone)
    return _normalize(saved)


class SetActiveRequest(BaseModel):
    active: bool


@router.patch("/{package_id}/active")
def set_package_active(package_id: str, body: SetActiveRequest) -> dict[str, Any]:
    repo = _repo()
    if not repo.update_one(package_id, {"is_active": body.active}):
        raise HTTPException(status_code=404, detail="Resource package not found")
    return _normalize(repo.find_by_id(package_id))


@router.get("/for-resource/{resource_type}/{resource_id}")
def packages_for_resource(resource_type: str, resource_id: int) -> list[dict[str, Any]]:
    """List every active package that names this resource anywhere in its
    membership (fixed/preferred/optional). Used by check-in integration
    (Stage 4) to surface "this person's standing package" on check-in."""
    if not is_known_resource_type(resource_type):
        raise HTTPException(status_code=400, detail=f"Unknown resource_type: {resource_type!r}")
    repo = _repo()
    docs = repo.find_many(
        {
            "is_active": True,
            "resources": {"$elemMatch": {"resource_type": resource_type, "resource_id": resource_id}},
        },
        sort=[("name", 1)],
    )
    return [_normalize(d) for d in docs]
