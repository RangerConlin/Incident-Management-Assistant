"""Forms router — template management and per-incident form instance CRUD.

FormDataContext (context.py) is deliberately NOT cut over here. It reads from
meetings, narrative_entries, agency_contacts, subject, and other incident tables
that have not been migrated yet. It will be migrated in a later sweep once
those source modules are cut over.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from sarapp_db.mongo.collection_names import IncidentCollections, MasterCollections
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db

master_router = APIRouter()
incident_router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return str(uuid.uuid4())


def _ensure_int_ids(col) -> None:
    missing = list(col.find({"int_id": {"$exists": False}}, {"_id": 1}))
    if not missing:
        return
    top = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    next_id = (top["int_id"] + 1) if top else 1
    for doc in missing:
        col.update_one({"_id": doc["_id"]}, {"$set": {"int_id": next_id}})
        next_id += 1


def _next_int_id(col) -> int:
    top = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    return (top["int_id"] + 1) if top else 1


# ---------------------------------------------------------------------------
# Master data mapping
# ---------------------------------------------------------------------------

def _map_family(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc.get("int_id"),
        "code": doc.get("code", ""),
        "title": doc.get("title", ""),
        "description": doc.get("description"),
        "category": doc.get("category"),
        "default_agency": doc.get("default_agency"),
        "is_active": 1 if doc.get("is_active", True) else 0,
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
    }


def _map_template(doc: Dict[str, Any], include_version: bool = False) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "id": doc.get("int_id"),
        "family_id": doc.get("family_int_id"),
        "agency": doc.get("agency", ""),
        "system": doc.get("system"),
        "code": doc.get("code", ""),
        "title": doc.get("title", ""),
        "description": doc.get("description"),
        "status": doc.get("status", "active"),
        "current_version_id": doc.get("current_version_int_id"),
        "compatibility": doc.get("compatibility", {}),
        "tags": doc.get("tags", []),
        "created_by": doc.get("created_by"),
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
    }
    if include_version and doc.get("_current_version_doc"):
        result["current_version"] = _map_version(doc["_current_version_doc"])
    return result


def _map_version(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc.get("int_id"),
        "template_id": doc.get("template_int_id"),
        "version_number": doc.get("version_number"),
        "version_label": doc.get("version_label"),
        "effective_date": doc.get("effective_date"),
        "retired_date": doc.get("retired_date"),
        "layout": doc.get("layout", {}),
        "fields": doc.get("fields", []),
        "bindings": doc.get("bindings", []),
        "validation": doc.get("validation", []),
        "export_profiles": doc.get("export_profiles", {}),
        "source_asset_path": doc.get("source_asset_path"),
        "checksum": doc.get("checksum"),
        "change_summary": doc.get("change_summary"),
        "created_by": doc.get("created_by"),
        "created_at": doc.get("created_at", ""),
        "is_current": bool(doc.get("is_current", False)),
    }


# ---------------------------------------------------------------------------
# Instance mapping
# ---------------------------------------------------------------------------

def _instance_int_id(instance_id: str, incident_id: str) -> Optional[int]:
    marker = f"{incident_id}-FORM-"
    if isinstance(instance_id, str) and instance_id.startswith(marker):
        try:
            return int(instance_id[len(marker):])
        except ValueError:
            pass
    return None


def _next_instance_id(col, incident_id: str) -> str:
    all_ids = [d.get("instance_id", "") for d in col.find({"incident_id": incident_id}, {"instance_id": 1})]
    marker = f"{incident_id}-FORM-"
    max_n = max(
        (int(iid[len(marker):]) for iid in all_ids if isinstance(iid, str) and iid.startswith(marker)),
        default=0
    )
    return f"{marker}{max_n + 1}"


def _map_value_doc(field_key: str, vdoc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "field_key": field_key,
        "value": vdoc.get("value"),
        "display_value": vdoc.get("display_value"),
        "source_type": vdoc.get("source_type", "manual"),
        "source_binding": vdoc.get("source_binding"),
        "source_module": vdoc.get("source_module"),
        "source_record_id": vdoc.get("source_record_id"),
        "is_locked": bool(vdoc.get("is_locked", False)),
        "is_overridden": bool(vdoc.get("is_overridden", False)),
        "override_reason": vdoc.get("override_reason"),
        "updated_by": vdoc.get("updated_by"),
        "updated_at": vdoc.get("updated_at", ""),
    }


def _map_instance(doc: Dict[str, Any], incident_id: str, include_values: bool = False) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "id": _instance_int_id(doc.get("instance_id", ""), incident_id),
        "instance_id": doc.get("instance_id"),
        "family_id": doc.get("family_id"),
        "template_id": doc.get("template_id"),
        "template_version_id": doc.get("template_version_id"),
        "incident_id": doc.get("incident_id"),
        "operational_period_id": doc.get("operational_period_id"),
        "linked_module": doc.get("linked_module"),
        "linked_record_id": doc.get("linked_record_id"),
        "title": doc.get("title"),
        "agency": doc.get("agency"),
        "status": doc.get("status", "draft"),
        "revision_number": doc.get("revision_number", 1),
        "created_by": doc.get("created_by"),
        "created_at": doc.get("created_at", ""),
        "updated_by": doc.get("updated_by"),
        "updated_at": doc.get("updated_at", ""),
        "finalized_by": doc.get("finalized_by"),
        "finalized_at": doc.get("finalized_at"),
        "exported_pdf_path": doc.get("exported_pdf_path"),
        "metadata": doc.get("metadata", {}),
        "metadata_json": None,
    }
    if include_values:
        raw_values = doc.get("values") or {}
        result["values"] = {k: _map_value_doc(k, v) for k, v in raw_values.items()}
    return result


# ===========================================================================
# FORM FAMILIES
# ===========================================================================

@master_router.get("/families")
def list_families(code: Optional[str] = None, category: Optional[str] = None, active: Optional[bool] = None):
    col = get_master_db()[MasterCollections.FORM_FAMILIES]
    _ensure_int_ids(col)
    query: Dict[str, Any] = {}
    if code:
        query["code"] = code
    if category:
        query["category"] = category
    if active is not None:
        query["is_active"] = active
    docs = list(col.find(query, {"_id": 0}).sort("code", 1))
    return [_map_family(d) for d in docs]


@master_router.post("/families", status_code=201)
def create_family(body: Dict[str, Any] = Body(...)):
    col = get_master_db()[MasterCollections.FORM_FAMILIES]
    _ensure_int_ids(col)
    now = _utcnow()
    int_id = _next_int_id(col)
    doc = {
        "_id": _new_id(),
        "int_id": int_id,
        "code": body["code"],
        "title": body["title"],
        "description": body.get("description"),
        "category": body.get("category"),
        "default_agency": body.get("default_agency"),
        "is_active": bool(body.get("is_active", True)),
        "created_at": now,
        "updated_at": now,
    }
    col.insert_one(doc)
    return _map_family(col.find_one({"int_id": int_id}, {"_id": 0}))


@master_router.get("/families/{code}")
def get_family_by_code(code: str):
    col = get_master_db()[MasterCollections.FORM_FAMILIES]
    doc = col.find_one({"code": code}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Form family not found")
    return _map_family(doc)


# ===========================================================================
# FORM TEMPLATES
# ===========================================================================

@master_router.get("/templates")
def list_templates(
    family_code: Optional[str] = None,
    agency: Optional[str] = None,
    system: Optional[str] = None,
    status: Optional[str] = None,
    active_only: bool = False,
):
    tmpl_col = get_master_db()[MasterCollections.FORM_TEMPLATES]
    fam_col = get_master_db()[MasterCollections.FORM_FAMILIES]
    _ensure_int_ids(tmpl_col)
    query: Dict[str, Any] = {}
    if agency:
        query["agency"] = agency
    if system:
        query["system"] = system
    if status:
        query["status"] = status
    if active_only:
        query["status"] = "active"
    if family_code:
        fam = fam_col.find_one({"code": family_code}, {"int_id": 1})
        if not fam:
            return []
        query["family_int_id"] = fam["int_id"]
        if active_only:
            fam_active = fam_col.find_one({"code": family_code, "is_active": True})
            if not fam_active:
                return []
    docs = list(tmpl_col.find(query, {"_id": 0}).sort([("family_int_id", 1), ("agency", 1), ("code", 1)]))
    family_map = {d["int_id"]: d for d in fam_col.find({}, {"_id": 0})}
    results = []
    for d in docs:
        row = _map_template(d)
        fam = family_map.get(d.get("family_int_id"))
        if fam:
            row["family_code"] = fam.get("code", "")
            row["family_title"] = fam.get("title", "")
        results.append(row)
    return results


@master_router.post("/templates", status_code=201)
def create_template(body: Dict[str, Any] = Body(...)):
    tmpl_col = get_master_db()[MasterCollections.FORM_TEMPLATES]
    _ensure_int_ids(tmpl_col)
    now = _utcnow()
    int_id = _next_int_id(tmpl_col)
    doc = {
        "_id": _new_id(),
        "int_id": int_id,
        "family_int_id": body["family_id"],
        "agency": body.get("agency", ""),
        "system": body.get("system"),
        "code": body.get("code", ""),
        "title": body.get("title", ""),
        "description": body.get("description"),
        "status": body.get("status", "active"),
        "current_version_int_id": None,
        "compatibility": body.get("compatibility", {}),
        "tags": body.get("tags", []),
        "created_by": body.get("created_by"),
        "created_at": now,
        "updated_at": now,
    }
    tmpl_col.insert_one(doc)
    return _map_template(tmpl_col.find_one({"int_id": int_id}, {"_id": 0}))


@master_router.get("/templates/{template_id}")
def get_template(template_id: int):
    tmpl_col = get_master_db()[MasterCollections.FORM_TEMPLATES]
    ver_col = get_master_db()[MasterCollections.FORM_TEMPLATE_VERSIONS]
    doc = tmpl_col.find_one({"int_id": template_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Template not found")
    result = _map_template(doc)
    if doc.get("current_version_int_id"):
        ver = ver_col.find_one({"int_id": doc["current_version_int_id"]}, {"_id": 0})
        if ver:
            result["current_version"] = _map_version(ver)
    return result


@master_router.patch("/templates/{template_id}/retire")
def retire_template(template_id: int, user_id: Optional[str] = None):
    tmpl_col = get_master_db()[MasterCollections.FORM_TEMPLATES]
    result = tmpl_col.update_one({"int_id": template_id}, {"$set": {"status": "retired", "updated_at": _utcnow()}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")


# ===========================================================================
# FORM TEMPLATE VERSIONS
# ===========================================================================

@master_router.get("/templates/{template_id}/versions/current")
def get_current_version(template_id: int):
    tmpl_col = get_master_db()[MasterCollections.FORM_TEMPLATES]
    ver_col = get_master_db()[MasterCollections.FORM_TEMPLATE_VERSIONS]
    tmpl = tmpl_col.find_one({"int_id": template_id}, {"_id": 0})
    if not tmpl or not tmpl.get("current_version_int_id"):
        raise HTTPException(status_code=404, detail="No current version found")
    ver = ver_col.find_one({"int_id": tmpl["current_version_int_id"]}, {"_id": 0})
    if not ver:
        raise HTTPException(status_code=404, detail="Version not found")
    return _map_version(ver)


@master_router.get("/templates/{template_id}/versions")
def list_template_versions(template_id: int):
    ver_col = get_master_db()[MasterCollections.FORM_TEMPLATE_VERSIONS]
    _ensure_int_ids(ver_col)
    docs = list(ver_col.find({"template_int_id": template_id}, {"_id": 0}).sort("version_number", 1))
    return [_map_version(d) for d in docs]


@master_router.get("/templates/{template_id}/versions/{version_id}")
def get_template_version(template_id: int, version_id: int):
    ver_col = get_master_db()[MasterCollections.FORM_TEMPLATE_VERSIONS]
    doc = ver_col.find_one({"template_int_id": template_id, "int_id": version_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Version not found")
    return _map_version(doc)


@master_router.post("/templates/{template_id}/versions", status_code=201)
def create_template_version(template_id: int, body: Dict[str, Any] = Body(...)):
    tmpl_col = get_master_db()[MasterCollections.FORM_TEMPLATES]
    ver_col = get_master_db()[MasterCollections.FORM_TEMPLATE_VERSIONS]
    _ensure_int_ids(ver_col)
    now = _utcnow()
    int_id = _next_int_id(ver_col)
    ver_col.update_many({"template_int_id": template_id}, {"$set": {"is_current": False}})
    doc = {
        "_id": _new_id(),
        "int_id": int_id,
        "template_int_id": template_id,
        "version_number": body["version_number"],
        "version_label": body.get("version_label"),
        "effective_date": body.get("effective_date"),
        "retired_date": body.get("retired_date"),
        "layout": body.get("layout", {}),
        "fields": body.get("fields", []),
        "bindings": body.get("bindings", []),
        "validation": body.get("validation", []),
        "export_profiles": body.get("export_profiles", {}),
        "source_asset_path": body.get("source_asset_path"),
        "checksum": body.get("checksum"),
        "change_summary": body.get("change_summary"),
        "created_by": body.get("created_by"),
        "created_at": now,
        "is_current": True,
    }
    ver_col.insert_one(doc)
    tmpl_col.update_one({"int_id": template_id}, {"$set": {"current_version_int_id": int_id, "updated_at": now}})
    return _map_version(ver_col.find_one({"int_id": int_id}, {"_id": 0}))


# ===========================================================================
# FORM INSTANCES
# ===========================================================================

@incident_router.get("/incidents/{incident_id}/forms")
def list_instances(
    incident_id: str,
    agency: Optional[str] = None,
    status: Optional[str] = None,
    operational_period_id: Optional[str] = None,
    linked_module: Optional[str] = None,
    linked_record_id: Optional[str] = None,
):
    col = get_incident_db(incident_id)[IncidentCollections.FORMS]
    query: Dict[str, Any] = {"incident_id": incident_id, "deleted": {"$ne": True}}
    for field, val in [("agency", agency), ("status", status), ("operational_period_id", operational_period_id), ("linked_module", linked_module), ("linked_record_id", linked_record_id)]:
        if val:
            query[field] = val
    docs = list(col.find(query, {"_id": 0}).sort("updated_at", -1))
    return [_map_instance(d, incident_id) for d in docs]


class CreateInstanceRequest(BaseModel):
    family_id: int
    template_id: int
    template_version_id: int
    title: Optional[str] = None
    agency: Optional[str] = None
    status: str = "draft"
    revision_number: int = 1
    created_by: Optional[str] = None
    operational_period_id: Optional[str] = None
    linked_module: Optional[str] = None
    linked_record_id: Optional[str] = None
    metadata: Dict[str, Any] = {}


@incident_router.post("/incidents/{incident_id}/forms", status_code=201)
def create_instance(incident_id: str, body: CreateInstanceRequest):
    col = get_incident_db(incident_id)[IncidentCollections.FORMS]
    audit_col = get_incident_db(incident_id)[IncidentCollections.FORM_INSTANCE_AUDIT]
    links_col = get_incident_db(incident_id)[IncidentCollections.FORM_INSTANCE_LINKS]
    now = _utcnow()
    instance_id = _next_instance_id(col, incident_id)
    doc = {
        "_id": _new_id(),
        "instance_id": instance_id,
        "incident_id": incident_id,
        "family_id": body.family_id,
        "template_id": body.template_id,
        "template_version_id": body.template_version_id,
        "operational_period_id": body.operational_period_id,
        "linked_module": body.linked_module,
        "linked_record_id": body.linked_record_id,
        "title": body.title,
        "agency": body.agency,
        "status": body.status,
        "revision_number": body.revision_number,
        "created_by": body.created_by,
        "created_at": now,
        "updated_by": body.created_by,
        "updated_at": now,
        "finalized_by": None,
        "finalized_at": None,
        "exported_pdf_path": None,
        "metadata": body.metadata or {},
        "values": {},
        "deleted": False,
    }
    col.insert_one(doc)
    rev_col = get_incident_db(incident_id)[IncidentCollections.FORM_INSTANCE_REVISIONS]
    _write_instance_audit(audit_col, instance_id, None, "created", None, {"status": "draft"}, body.created_by, {})
    _write_instance_revision(col, rev_col, instance_id, incident_id, body.revision_number, "created", body.created_by)
    if body.linked_module and body.linked_record_id:
        links_col.insert_one({
            "_id": _new_id(),
            "instance_id": instance_id,
            "linked_module": body.linked_module,
            "linked_record_id": body.linked_record_id,
            "relationship_type": "source",
            "created_by": body.created_by,
            "created_at": now,
        })
    saved = col.find_one({"instance_id": instance_id}, {"_id": 0})
    return _map_instance(saved, incident_id, include_values=True)


def _write_instance_audit(col, instance_id: str, field_key: Optional[str], action: str, old_value: Any, new_value: Any, user_id: Optional[str], details: Dict[str, Any]) -> None:
    col.insert_one({
        "_id": _new_id(),
        "instance_id": instance_id,
        "field_key": field_key,
        "action": action,
        "old_value": old_value,
        "new_value": new_value,
        "user_id": user_id,
        "timestamp": _utcnow(),
        "details": details,
    })


def _write_instance_revision(forms_col, rev_col, instance_id: str, incident_id: str, revision_number: int, summary: str, user_id: Optional[str]) -> None:
    doc = forms_col.find_one({"instance_id": instance_id}, {"_id": 0})
    if not doc:
        return
    rev_col.update_one(
        {"instance_id": instance_id, "revision_number": revision_number},
        {"$setOnInsert": {
            "_id": _new_id(),
            "instance_id": instance_id,
            "revision_number": revision_number,
            "snapshot": doc,
            "change_summary": summary,
            "created_by": user_id,
            "created_at": _utcnow(),
        }},
        upsert=True,
    )


@incident_router.get("/incidents/{incident_id}/forms/{instance_id}")
def get_instance(incident_id: str, instance_id: int):
    col = get_incident_db(incident_id)[IncidentCollections.FORMS]
    compound_id = f"{incident_id}-FORM-{instance_id}"
    doc = col.find_one({"instance_id": compound_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Form instance not found")
    return _map_instance(doc, incident_id, include_values=True)


class UpsertValuesRequest(BaseModel):
    updates: Dict[str, Dict[str, Any]]
    user_id: Optional[str] = None
    require_override_reason: bool = True


@incident_router.patch("/incidents/{incident_id}/forms/{instance_id}/values")
def upsert_values(incident_id: str, instance_id: int, body: UpsertValuesRequest):
    col = get_incident_db(incident_id)[IncidentCollections.FORMS]
    audit_col = get_incident_db(incident_id)[IncidentCollections.FORM_INSTANCE_AUDIT]
    rev_col = get_incident_db(incident_id)[IncidentCollections.FORM_INSTANCE_REVISIONS]
    compound_id = f"{incident_id}-FORM-{instance_id}"
    doc = col.find_one({"instance_id": compound_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Form instance not found")
    if doc.get("status") == "finalized":
        raise HTTPException(status_code=422, detail="finalized form cannot be edited unless reopened")
    now = _utcnow()
    existing_values = doc.get("values") or {}
    value_updates: Dict[str, Any] = {}
    for key, payload in body.updates.items():
        old_vdoc = existing_values.get(key, {})
        if old_vdoc.get("is_locked"):
            raise HTTPException(status_code=422, detail=f"field is locked: {key}")
        if body.require_override_reason and payload.get("is_overridden") and not payload.get("override_reason"):
            raise HTTPException(status_code=422, detail=f"override reason is required for {key}")
        new_vdoc = {
            "value": payload.get("value"),
            "display_value": payload.get("display_value"),
            "source_type": payload.get("source_type", "manual"),
            "source_binding": payload.get("source_binding"),
            "source_module": payload.get("source_module"),
            "source_record_id": payload.get("source_record_id"),
            "is_locked": bool(payload.get("is_locked", False)),
            "is_overridden": bool(payload.get("is_overridden", False)),
            "override_reason": payload.get("override_reason"),
            "updated_by": body.user_id,
            "updated_at": now,
        }
        value_updates[f"values.{key}"] = new_vdoc
        _write_instance_audit(audit_col, compound_id, key, "value_updated", old_vdoc or None, payload, body.user_id, {"source_type": payload.get("source_type", "manual")})
    new_revision = int(doc.get("revision_number", 1)) + 1
    value_updates["revision_number"] = new_revision
    value_updates["updated_by"] = body.user_id
    value_updates["updated_at"] = now
    col.update_one({"instance_id": compound_id}, {"$set": value_updates})
    _write_instance_revision(col, rev_col, compound_id, incident_id, new_revision, "values saved", body.user_id)
    updated = col.find_one({"instance_id": compound_id}, {"_id": 0})
    return _map_instance(updated, incident_id, include_values=True)


class FinalizeRequest(BaseModel):
    user_id: Optional[str] = None


@incident_router.post("/incidents/{incident_id}/forms/{instance_id}/finalize")
def finalize_instance(incident_id: str, instance_id: int, body: FinalizeRequest):
    col = get_incident_db(incident_id)[IncidentCollections.FORMS]
    audit_col = get_incident_db(incident_id)[IncidentCollections.FORM_INSTANCE_AUDIT]
    rev_col = get_incident_db(incident_id)[IncidentCollections.FORM_INSTANCE_REVISIONS]
    compound_id = f"{incident_id}-FORM-{instance_id}"
    doc = col.find_one({"instance_id": compound_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Form instance not found")
    if doc.get("status") == "finalized":
        return _map_instance(doc, incident_id, include_values=True)
    now = _utcnow()
    new_revision = int(doc.get("revision_number", 1)) + 1
    lock_updates = {f"values.{k}.is_locked": True for k in (doc.get("values") or {})}
    updates = {"status": "finalized", "finalized_by": body.user_id, "finalized_at": now, "updated_by": body.user_id, "updated_at": now, "revision_number": new_revision, **lock_updates}
    col.update_one({"instance_id": compound_id}, {"$set": updates})
    _write_instance_audit(audit_col, compound_id, None, "finalized", None, {"status": "finalized"}, body.user_id, {})
    _write_instance_revision(col, rev_col, compound_id, incident_id, new_revision, "finalized", body.user_id)
    updated = col.find_one({"instance_id": compound_id}, {"_id": 0})
    return _map_instance(updated, incident_id, include_values=True)


class ReopenRequest(BaseModel):
    user_id: Optional[str] = None
    reason: Optional[str] = None


@incident_router.post("/incidents/{incident_id}/forms/{instance_id}/reopen")
def reopen_instance(incident_id: str, instance_id: int, body: ReopenRequest):
    col = get_incident_db(incident_id)[IncidentCollections.FORMS]
    audit_col = get_incident_db(incident_id)[IncidentCollections.FORM_INSTANCE_AUDIT]
    rev_col = get_incident_db(incident_id)[IncidentCollections.FORM_INSTANCE_REVISIONS]
    compound_id = f"{incident_id}-FORM-{instance_id}"
    doc = col.find_one({"instance_id": compound_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Form instance not found")
    now = _utcnow()
    new_revision = int(doc.get("revision_number", 1)) + 1
    col.update_one({"instance_id": compound_id}, {"$set": {"status": "draft", "finalized_by": None, "finalized_at": None, "updated_by": body.user_id, "updated_at": now, "revision_number": new_revision}})
    _write_instance_audit(audit_col, compound_id, None, "reopened", None, {"status": "draft"}, body.user_id, {"reason": body.reason})
    _write_instance_revision(col, rev_col, compound_id, incident_id, new_revision, "reopened", body.user_id)
    updated = col.find_one({"instance_id": compound_id}, {"_id": 0})
    return _map_instance(updated, incident_id, include_values=True)


@incident_router.patch("/incidents/{incident_id}/forms/{instance_id}/exported-pdf")
def set_exported_pdf(incident_id: str, instance_id: int, path: str, user_id: Optional[str] = None):
    col = get_incident_db(incident_id)[IncidentCollections.FORMS]
    compound_id = f"{incident_id}-FORM-{instance_id}"
    result = col.update_one({"instance_id": compound_id}, {"$set": {"exported_pdf_path": path, "updated_by": user_id, "updated_at": _utcnow()}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Form instance not found")


@incident_router.post("/incidents/{incident_id}/forms/{instance_id}/exports", status_code=201)
def create_export_record(incident_id: str, instance_id: int, body: Dict[str, Any] = Body(...)):
    col = get_incident_db(incident_id)[IncidentCollections.FORM_INSTANCE_EXPORTS]
    compound_id = f"{incident_id}-FORM-{instance_id}"
    now = _utcnow()
    doc = {
        "_id": _new_id(),
        "instance_id": compound_id,
        "export_type": body["export_type"],
        "export_path": body["export_path"],
        "template_version_id": body["template_version_id"],
        "revision_number": body["revision_number"],
        "created_by": body.get("created_by"),
        "created_at": now,
        "checksum": body.get("checksum"),
    }
    col.insert_one(doc)
    return {**doc, "_id": None, "id": None}


@incident_router.get("/incidents/{incident_id}/forms/{instance_id}/revisions")
def list_revisions(incident_id: str, instance_id: int):
    col = get_incident_db(incident_id)[IncidentCollections.FORM_INSTANCE_REVISIONS]
    compound_id = f"{incident_id}-FORM-{instance_id}"
    docs = list(col.find({"instance_id": compound_id}, {"_id": 0}).sort("revision_number", 1))
    return docs


@incident_router.get("/incidents/{incident_id}/forms/{instance_id}/audit")
def list_audit(incident_id: str, instance_id: int):
    col = get_incident_db(incident_id)[IncidentCollections.FORM_INSTANCE_AUDIT]
    compound_id = f"{incident_id}-FORM-{instance_id}"
    docs = list(col.find({"instance_id": compound_id}, {"_id": 0}).sort([("timestamp", 1), ("_id", 1)]))
    return docs
