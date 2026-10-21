"""Cross-module helpers for referring to "an individual master resource".

Resource Associations (Stage 2) and Resource Packages (Stage 3) both need to
reference a personnel/vehicle/aircraft/equipment record by a
(resource_type, resource_id) pair without caring which master collection or
dual-key field backs that particular kind. This module is the one place
that mapping lives, so every router stays in sync with the dual-key
local/central pattern each master collection already uses (see
int_id.dual_key_field and docs/archive/design-documents/Instructions/
mongodb_schema_decisions.md's "Personnel: central-vs-local record ids").
"""
from __future__ import annotations

from typing import Any, Optional

from pymongo.database import Database

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.int_id import dual_key_field

# resource_type key -> (collection name, local record field, central/master record field)
RESOURCE_KIND_FIELDS: dict[str, tuple[str, str, str]] = {
    "personnel": (MasterCollections.PERSONNEL, "person_record", "person_record_master"),
    "vehicle": (MasterCollections.VEHICLES, "vehicle_record", "vehicle_record_master"),
    "aircraft": (MasterCollections.AIRCRAFT, "aircraft_record", "aircraft_record_master"),
    "equipment": (MasterCollections.EQUIPMENT, "equipment_record", "equipment_record_master"),
}

RESOURCE_KINDS: tuple[str, ...] = tuple(RESOURCE_KIND_FIELDS.keys())


def is_known_resource_type(resource_type: str) -> bool:
    return resource_type in RESOURCE_KIND_FIELDS


def collection_name_for(resource_type: str) -> str:
    if resource_type not in RESOURCE_KIND_FIELDS:
        raise ValueError(f"Unknown resource_type: {resource_type!r}. Expected one of {RESOURCE_KINDS}.")
    return RESOURCE_KIND_FIELDS[resource_type][0]


def record_field_for(db: Database, resource_type: str) -> str:
    if resource_type not in RESOURCE_KIND_FIELDS:
        raise ValueError(f"Unknown resource_type: {resource_type!r}. Expected one of {RESOURCE_KINDS}.")
    _, local_field, master_field = RESOURCE_KIND_FIELDS[resource_type]
    return dual_key_field(db, local_field, master_field)


def find_resource(db: Database, resource_type: str, resource_id: int) -> Optional[dict[str, Any]]:
    """Return the master document for (resource_type, resource_id), or None
    if the resource type is unknown, the id doesn't exist, or it's
    soft-deleted."""
    if not is_known_resource_type(resource_type):
        return None
    collection = db[collection_name_for(resource_type)]
    field = record_field_for(db, resource_type)
    doc = collection.find_one({field: resource_id})
    if doc is not None and doc.get("deleted") is True:
        return None
    return doc


def resource_display_name(doc: Optional[dict[str, Any]], resource_type: str) -> str:
    """Best-effort human label for a resource document, used in UI payloads."""
    if not doc:
        return ""
    if resource_type == "personnel":
        return str(doc.get("name") or doc.get("callsign") or "")
    if resource_type == "vehicle":
        return str(
            doc.get("vehicle_id")
            or doc.get("license_plate")
            or " ".join(filter(None, [doc.get("make"), doc.get("model")])).strip()
            or ""
        )
    if resource_type == "aircraft":
        return str(doc.get("tail_number") or doc.get("callsign") or doc.get("aircraft_id") or "")
    if resource_type == "equipment":
        return str(doc.get("name") or doc.get("equipment_id") or "")
    return ""
