"""Browser-based CRUD GUI for the central master-catalog database.

No master-data-editing web GUI exists anywhere else in the product — today
master data is only edited through the desktop app's admin panels over
LAN/localhost (see `Design Documents/Instructions/cloud_router_architecture.md`
"Central Master Database"). This is the MVP: a handful of collections
(personnel, equipment — more to follow once this shape proves out, see
`backlog.md`), each with a plain list/create/edit/delete view.

This does **not** talk to Mongo directly. Each `CollectionSpec` below wraps
the *existing* master-catalog router functions in
`data/db/sarapp_db/api/routers/` — the exact same functions the
`/central-master/api/master/...` HTTP routes call — so every write still
goes through `BaseRepository`. Calling them as plain Python functions
in-process (rather than looping an HTTP call back into this same app) is
just an optimization; the code path is identical to issuing those requests.

No schema-introspection magic: `personnel.py`/`equipment.py` (like most
master routers) take loose `dict[str, Any]` bodies, not strict Pydantic
request models, so each collection's editable fields are declared explicitly
below rather than derived from a schema that doesn't exist at runtime.
"""

from __future__ import annotations

import csv
import hmac
import io
import json
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Any, Callable, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from master_db.config import MasterGuiSettings, hash_password, load_settings

_SESSION_COOKIE = "sarapp_central_master_session"
_SESSION_MAX_AGE_SECONDS = 12 * 60 * 60


@dataclass(frozen=True)
class FieldSpec:
    name: str
    label: str
    input_type: str = "text"  # "text" | "checkbox" | "textarea"
    value_type: str = "str"  # "str" | "int" | "float" | "bool"


@dataclass(frozen=True)
class CollectionSpec:
    key: str
    title: str
    record_field: str
    fields: list[FieldSpec]
    list_fn: Callable[[], list[dict[str, Any]]]
    get_fn: Callable[[int], dict[str, Any]]
    create_fn: Callable[[dict[str, Any]], dict[str, Any]]
    update_fn: Callable[[int, dict[str, Any]], dict[str, Any]]
    delete_fn: Optional[Callable[[int], None]]
    # Import/export use a separate, usually larger field list than the
    # on-page edit form above — matching the desktop Edit-menu panel's
    # column set exactly (shared via modules.personnel.catalog_io /
    # modules.logistics.equipment_catalog_io) so a file exported from one
    # is importable into the other. `export_row_fn`/`import_payload_fn`
    # default to a flat passthrough over `export_fields` for collections
    # with no special row-shaping (e.g. equipment); personnel supplies its
    # own to handle emergency/contact-info grouping and certification
    # code parsing, same as the desktop panel.
    export_fields: list[str] = dc_field(default_factory=list)
    export_field_labels: dict[str, str] = dc_field(default_factory=dict)
    export_row_fn: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None
    import_payload_fn: Optional[Callable[[dict[str, str]], dict[str, Any]]] = None
    form_row_fn: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None
    form_payload_fn: Optional[Callable[[dict[str, str]], dict[str, Any]]] = None
    # Per-field override for the list-table cell's displayed text — e.g.
    # showing a foreign key's resolved name instead of its raw int id.
    # Keyed by FieldSpec.name; falls back to the raw field value when a
    # field has no entry here.
    list_cell_fn: Optional[Callable[[dict[str, Any], str], Any]] = None
    # Subset of `fields` (by name) shown as columns in the list-table view.
    # None means show every field in `fields`. Keeps wide records (e.g.
    # personnel's emergency-contact/certification fields) off the grid
    # while still editable on the record's own page. "sort_order" is
    # always dropped from the grid separately (see list_collection), so it
    # does not need to be excluded here too.
    list_fields: Optional[list[str]] = None


def _field_keys(spec: CollectionSpec) -> list[str]:
    return spec.export_fields or [field.name for field in spec.fields]


def _field_labels(spec: CollectionSpec) -> dict[str, str]:
    labels = {field.name: field.label for field in spec.fields}
    labels.update(spec.export_field_labels)
    return labels


def _gui_users_repo():
    from sarapp_db.mongo.database_manager import get_master_db
    from sarapp_db.mongo.repository import BaseRepository

    class MasterGuiUsersRepository(BaseRepository):
        collection_name = "master_gui_users"
        soft_deletes = False

    return MasterGuiUsersRepository(get_master_db())


def _next_gui_user_id() -> int:
    repo = _gui_users_repo()
    docs = repo.find_many({}, sort=[("int_id", -1)], limit=1)
    return (docs[0].get("int_id", 0) if docs else 0) + 1


def _serialize_gui_user(doc: dict[str, Any] | None) -> dict[str, Any]:
    if doc is None:
        raise HTTPException(status_code=404, detail="Console user not found")
    payload = dict(doc)
    payload.pop("_id", None)
    payload.pop("password_hash", None)
    payload["id"] = payload.get("int_id")
    payload["password"] = ""
    return payload


def _list_gui_users() -> list[dict[str, Any]]:
    return [_serialize_gui_user(doc) for doc in _gui_users_repo().find_many({}, sort=[("username", 1)])]


def _get_gui_user(user_id: int) -> dict[str, Any]:
    return _serialize_gui_user(_gui_users_repo().find_one({"int_id": user_id}))


def _create_gui_user(body: dict[str, Any]) -> dict[str, Any]:
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    if not password:
        raise HTTPException(status_code=400, detail="Password is required")
    repo = _gui_users_repo()
    if repo.find_one({"username": username}):
        raise HTTPException(status_code=409, detail="Username already exists")
    doc = repo.insert_one({
        "int_id": _next_gui_user_id(),
        "username": username,
        "password_hash": hash_password(password),
        "is_active": int(bool(body.get("is_active", 1))),
        "notes": str(body.get("notes") or "").strip(),
    })
    return _serialize_gui_user(doc)


def _update_gui_user(user_id: int, body: dict[str, Any]) -> dict[str, Any]:
    repo = _gui_users_repo()
    existing = repo.find_one({"int_id": user_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Console user not found")
    updates: dict[str, Any] = {
        "username": str(body.get("username") or "").strip(),
        "is_active": int(bool(body.get("is_active", 0))),
        "notes": str(body.get("notes") or "").strip(),
    }
    if not updates["username"]:
        raise HTTPException(status_code=400, detail="Username is required")
    duplicate = repo.find_one({"username": updates["username"]})
    if duplicate and duplicate.get("int_id") != user_id:
        raise HTTPException(status_code=409, detail="Username already exists")
    password = str(body.get("password") or "").strip()
    if password:
        updates["password_hash"] = hash_password(password)
    repo.update_one(existing["_id"], updates)
    return _serialize_gui_user(repo.find_by_id(existing["_id"]))


def _delete_gui_user(user_id: int) -> None:
    repo = _gui_users_repo()
    existing = repo.find_one({"int_id": user_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Console user not found")
    repo.delete_one(existing["_id"])


def _gui_user_valid(username: str, password: str) -> bool:
    doc = _gui_users_repo().find_one({"username": username})
    if not doc or not int(doc.get("is_active", 1)):
        return False
    return hmac.compare_digest(hash_password(password), str(doc.get("password_hash") or ""))


def _vehicle_create_payload(vehicle_body_cls: type, body: dict[str, Any]) -> Any:
    payload = {key: value for key, value in body.items() if value is not None}
    return vehicle_body_cls(**payload)


def _rank_display_text(rank_row: dict[str, Any]) -> str:
    code = str(rank_row.get("rank_code") or "").strip()
    name = str(rank_row.get("rank_name") or rank_row.get("name") or "").strip()
    short = str(rank_row.get("short_display") or "").strip()
    if code and name:
        return f"{code} - {name}"
    return short or code or name


def _org_type_id_by_name(name: Any) -> int | None:
    from sarapp_db.api.routers import organizations as organizations_router

    wanted = str(name or "").strip().lower()
    if not wanted:
        return None
    for row in organizations_router.list_org_types(search=""):
        if str(row.get("name") or "").strip().lower() == wanted:
            try:
                return int(row.get("int_id"))
            except (TypeError, ValueError):
                return None
    return None


def _organization_id_by_name(name: Any) -> int | None:
    from sarapp_db.api.routers import organizations as organizations_router

    wanted = str(name or "").strip().lower()
    if not wanted:
        return None
    for row in organizations_router.list_organizations(search=""):
        if str(row.get("name") or "").strip().lower() == wanted:
            try:
                return int(row.get("int_id"))
            except (TypeError, ValueError):
                return None
    return None


def _rank_structure_id_by_name(name: Any) -> int | None:
    from sarapp_db.api.routers import organizations as organizations_router

    wanted = str(name or "").strip().lower()
    if not wanted:
        return None
    for row in organizations_router.list_rank_structures(search=""):
        if str(row.get("name") or "").strip().lower() == wanted:
            try:
                return int(row.get("int_id"))
            except (TypeError, ValueError):
                return None
    return None


def _organization_list_cell(doc: dict[str, Any], field_name: str) -> Any:
    if field_name == "parent_organization_id":
        return doc.get("parent_organization_name") or doc.get(field_name)
    if field_name == "organization_type_id":
        return doc.get("organization_type_name") or doc.get(field_name)
    if field_name == "default_rank_structure_id":
        return doc.get("default_rank_structure_name") or doc.get("effective_rank_structure_name") or doc.get(field_name)
    return doc.get(field_name)


def _rank_structure_list_cell(doc: dict[str, Any], field_name: str) -> Any:
    if field_name == "organization_type_id":
        return doc.get("organization_type_name") or doc.get(field_name)
    return doc.get(field_name)


def _rank_structure_import_payload(row: dict[str, str]) -> dict[str, Any]:
    payload = _coerce_fields_payload(_rank_structure_fields(), row)
    org_type_name = row.get("organization_type_name")
    if org_type_name and payload.get("organization_type_id") is None:
        payload["organization_type_id"] = _org_type_id_by_name(org_type_name)
    return payload


def _organization_import_payload(row: dict[str, str]) -> dict[str, Any]:
    payload = _coerce_fields_payload(_organization_fields(), row)
    structure_name = row.get("default_rank_structure_name")
    if structure_name and payload.get("default_rank_structure_id") is None:
        payload["default_rank_structure_id"] = _rank_structure_id_by_name(structure_name)
    type_name = row.get("organization_type_name")
    if type_name and payload.get("organization_type_id") is None:
        payload["organization_type_id"] = _org_type_id_by_name(type_name)
    parent_name = row.get("parent_organization_name")
    if parent_name and payload.get("parent_organization_id") is None:
        payload["parent_organization_id"] = _organization_id_by_name(parent_name)
    return payload


def _rank_import_payload(row: dict[str, str]) -> dict[str, Any]:
    payload = _coerce_fields_payload(_rank_fields(), row)
    structure_name = row.get("rank_structure_name")
    if structure_name and payload.get("rank_structure_id") is None:
        payload["rank_structure_id"] = _rank_structure_id_by_name(structure_name)
    return payload


def _rank_structure_fields() -> list[FieldSpec]:
    return [
        FieldSpec("name", "Name"),
        FieldSpec("description", "Description", input_type="textarea"),
        FieldSpec("organization_type_id", "Organization Type ID", value_type="int"),
        FieldSpec("is_template", "Template", input_type="checkbox", value_type="int"),
        FieldSpec("is_system_template", "System Template", input_type="checkbox", value_type="int"),
        FieldSpec("sort_order", "Sort Order", value_type="int"),
        FieldSpec("is_active", "Active", input_type="checkbox", value_type="int"),
    ]


def _organization_fields() -> list[FieldSpec]:
    return [
        FieldSpec("name", "Name"),
        FieldSpec("short_name", "Short Name"),
        FieldSpec("parent_organization_id", "Parent Organization ID", input_type="select_fk", value_type="int"),
        FieldSpec("organization_type_id", "Organization Type ID", input_type="select_fk", value_type="int"),
        FieldSpec("default_rank_structure_id", "Default Rank Structure ID", input_type="select_fk", value_type="int"),
        FieldSpec("callsign_prefix", "Callsign Prefix"),
        FieldSpec("external_id", "External ID"),
        FieldSpec("address", "Address", input_type="textarea"),
        FieldSpec("latitude", "Latitude", value_type="float"),
        FieldSpec("longitude", "Longitude", value_type="float"),
        FieldSpec("notes", "Notes", input_type="textarea"),
        FieldSpec("sort_order", "Sort Order", value_type="int"),
        FieldSpec("is_active", "Active", input_type="checkbox", value_type="int"),
    ]


def _rank_fields() -> list[FieldSpec]:
    return [
        FieldSpec("rank_structure_id", "Rank Structure ID", value_type="int"),
        FieldSpec("rank_code", "Rank Code"),
        FieldSpec("rank_name", "Rank Name"),
        FieldSpec("short_display", "Short Display"),
        FieldSpec("sort_order", "Sort Order", value_type="int"),
        FieldSpec("is_active", "Active", input_type="checkbox", value_type="int"),
    ]


def _personnel_org_rank_options() -> dict[str, Any]:
    from sarapp_db.api.routers import organizations as organizations_router

    orgs = organizations_router.list_organizations(search="")
    rank_structures = {
        int(row.get("int_id")): organizations_router.list_ranks(
            structure_id=int(row.get("int_id")), search=""
        )
        for row in organizations_router.list_rank_structures(search="")
        if row.get("int_id") is not None
    }
    rank_by_org: dict[str, list[str]] = {}
    org_options: list[tuple[str, str]] = []
    for org in orgs:
        name = str(org.get("name") or "").strip()
        if not name or not int(org.get("is_active", 1)):
            continue
        short_name = str(org.get("short_name") or "").strip()
        org_options.append((name, f"{short_name} - {name}" if short_name else name))
        structure_id = org.get("effective_rank_structure_id")
        try:
            ranks = rank_structures.get(int(structure_id), []) if structure_id is not None else []
        except (TypeError, ValueError):
            ranks = []
        rank_options: list[str] = []
        for rank in ranks:
            display = _rank_display_text(rank)
            if display and int(rank.get("is_active", 1)):
                rank_options.append(display)
        rank_by_org[name] = rank_options
    return {
        "organization_options": sorted(org_options, key=lambda pair: pair[1].lower()),
        "rank_by_org": rank_by_org,
    }


def _build_collection_specs() -> dict[str, CollectionSpec]:
    # Imported lazily (not at module import time) so this module can be
    # imported without sarapp_db being on the path yet in contexts that
    # never actually serve the GUI.
    from sarapp_db.api.routers import personnel as personnel_router
    from sarapp_db.api.routers import equipment as equipment_router
    from sarapp_db.api.routers import organizations as organizations_router
    from sarapp_db.api.routers import vehicles as vehicles_router
    from modules.personnel.catalog_io import (
        PERSONNEL_FIELDS,
        PERSONNEL_FIELD_LABELS,
        build_personnel_import_payload,
        certification_catalogs,
        personnel_export_row,
    )
    from modules.logistics.equipment_catalog_io import FIELDS as EQUIPMENT_EXPORT_FIELDS

    personnel_catalog_by_code, personnel_catalog_by_id = certification_catalogs()
    equipment_export_field_keys = [f.key for f in EQUIPMENT_EXPORT_FIELDS]
    personnel_fields = [
        FieldSpec(
            f.key,
            f.label,
            input_type="select" if f.key in {"home_unit", "rank"} else "checkbox" if f.key == "is_medic" else "textarea" if f.key in {"notes", "contact_notes", "emergency_medical"} else "text",
        )
        for f in PERSONNEL_FIELDS
    ]
    equipment_fields = [
        FieldSpec(f.key, f.label, input_type="textarea" if f.key == "notes" else "text")
        for f in EQUIPMENT_EXPORT_FIELDS
    ]
    vehicle_fields = [
        FieldSpec("vehicle_id", "Vehicle ID"),
        FieldSpec("vin", "VIN"),
        FieldSpec("license_plate", "License Plate"),
        FieldSpec("year", "Year", value_type="int"),
        FieldSpec("make", "Make"),
        FieldSpec("model", "Model"),
        FieldSpec("capacity", "Capacity", value_type="int"),
        FieldSpec("type_id", "Type"),
        FieldSpec("status_id", "Status"),
        FieldSpec("organization", "Organization"),
        FieldSpec("resource_type_id", "Resource Type ID", value_type="int"),
        FieldSpec("tags", "Tags", input_type="textarea"),
    ]

    specs = [
        CollectionSpec(
            key="personnel",
            title="Personnel",
            record_field="person_record",
            fields=personnel_fields,
            # Called as plain Python functions, not through FastAPI's request
            # pipeline — any parameter whose real default is a
            # fastapi.params.Query/Body sentinel (not a plain Python value)
            # must be passed explicitly here, or the router function receives
            # the sentinel object itself instead of the value it stands in
            # for (it's truthy and has none of the real type's methods, so
            # this fails in confusing ways deep inside the function body).
            list_fn=lambda: personnel_router.list_personnel(search="", limit=10000),
            get_fn=personnel_router.get_person,
            create_fn=personnel_router.create_person,
            update_fn=lambda record_id, body: personnel_router.update_person(
                record_id, body, active_incident_id=None
            ),
            delete_fn=personnel_router.delete_person,
            export_fields=[f.key for f in PERSONNEL_FIELDS],
            export_field_labels=PERSONNEL_FIELD_LABELS,
            export_row_fn=lambda doc: personnel_export_row(doc, personnel_catalog_by_id),
            import_payload_fn=lambda row: build_personnel_import_payload(row, personnel_catalog_by_code),
            form_row_fn=lambda doc: personnel_export_row(doc, personnel_catalog_by_id),
            form_payload_fn=lambda row: build_personnel_import_payload(row, personnel_catalog_by_code),
            list_fields=["first_name", "last_name", "callsign", "rank", "home_unit", "phone", "is_medic"],
        ),
        CollectionSpec(
            key="equipment",
            title="Equipment",
            record_field="equipment_record",
            fields=equipment_fields,
            list_fn=lambda: equipment_router.list_equipment(search="", limit=10000),
            get_fn=equipment_router.get_equipment,
            create_fn=equipment_router.create_equipment,
            update_fn=equipment_router.update_equipment,
            delete_fn=equipment_router.delete_equipment,
            export_fields=equipment_export_field_keys,
            export_field_labels={f.key: f.label for f in EQUIPMENT_EXPORT_FIELDS},
            export_row_fn=lambda doc: {key: doc.get(key, "") for key in equipment_export_field_keys},
            import_payload_fn=lambda row: {
                key: row.get(key, "") for key in equipment_export_field_keys if row.get(key)
            },
        ),
        CollectionSpec(
            key="vehicles",
            title="Vehicles",
            record_field="vehicle_record",
            fields=vehicle_fields,
            list_fn=lambda: vehicles_router.list_vehicles(search="", status_filter="", type_filter=""),
            get_fn=vehicles_router.get_vehicle,
            create_fn=lambda body: vehicles_router.create_vehicle(
                _vehicle_create_payload(vehicles_router.VehicleBody, body)
            ),
            update_fn=vehicles_router.update_vehicle,
            delete_fn=vehicles_router.delete_vehicle,
        ),
        CollectionSpec(
            key="organization-types",
            title="Organization Types",
            record_field="int_id",
            fields=[
                FieldSpec("name", "Name"),
                FieldSpec("description", "Description", input_type="textarea"),
                FieldSpec("sort_order", "Sort Order", value_type="int"),
                FieldSpec("is_active", "Active", input_type="checkbox", value_type="int"),
            ],
            list_fn=lambda: organizations_router.list_org_types(search=""),
            get_fn=organizations_router.get_org_type,
            create_fn=organizations_router.create_org_type,
            update_fn=organizations_router.update_org_type,
            delete_fn=organizations_router.delete_org_type,
        ),
        CollectionSpec(
            key="rank-structures",
            title="Rank Structures",
            record_field="int_id",
            fields=_rank_structure_fields(),
            list_fn=lambda: organizations_router.list_rank_structures(search=""),
            get_fn=organizations_router.get_rank_structure,
            create_fn=organizations_router.create_rank_structure,
            update_fn=organizations_router.update_rank_structure,
            delete_fn=organizations_router.delete_rank_structure,
            export_fields=[
                "name", "description", "organization_type_id", "organization_type_name",
                "is_template", "is_system_template", "sort_order", "is_active",
            ],
            export_field_labels={
                "organization_type_name": "Organization Type Name",
            },
            import_payload_fn=_rank_structure_import_payload,
            list_cell_fn=_rank_structure_list_cell,
        ),
        CollectionSpec(
            key="organizations",
            title="Organizations",
            record_field="int_id",
            fields=_organization_fields(),
            list_fn=lambda: organizations_router.list_organizations(search=""),
            get_fn=organizations_router.get_organization,
            create_fn=organizations_router.create_organization,
            update_fn=organizations_router.update_organization,
            delete_fn=organizations_router.delete_organization,
            export_fields=[
                "name", "short_name", "parent_organization_id", "parent_organization_name",
                "organization_type_id", "organization_type_name",
                "default_rank_structure_id", "default_rank_structure_name",
                "callsign_prefix", "external_id", "address", "latitude", "longitude",
                "notes", "sort_order", "is_active",
            ],
            export_field_labels={
                "parent_organization_name": "Parent Organization Name",
                "organization_type_name": "Organization Type Name",
                "default_rank_structure_name": "Default Rank Structure Name",
            },
            import_payload_fn=_organization_import_payload,
            list_cell_fn=_organization_list_cell,
            list_fields=["name", "short_name", "parent_organization_id", "organization_type_id", "is_active"],
        ),
        CollectionSpec(
            key="ranks",
            title="Ranks",
            record_field="int_id",
            fields=_rank_fields(),
            list_fn=lambda: organizations_router.list_ranks(structure_id=None, search=""),
            get_fn=organizations_router.get_rank,
            create_fn=organizations_router.create_rank,
            update_fn=organizations_router.update_rank,
            delete_fn=organizations_router.delete_rank,
            export_fields=[
                "rank_structure_id", "rank_structure_name", "rank_code",
                "rank_name", "short_display", "sort_order", "is_active",
            ],
            export_field_labels={"rank_structure_name": "Rank Structure Name"},
            import_payload_fn=_rank_import_payload,
        ),
        CollectionSpec(
            key="console-users",
            title="Console Users",
            record_field="int_id",
            fields=[
                FieldSpec("username", "Username"),
                FieldSpec("password", "Password"),
                FieldSpec("is_active", "Active", input_type="checkbox", value_type="int"),
                FieldSpec("notes", "Notes", input_type="textarea"),
            ],
            list_fn=_list_gui_users,
            get_fn=_get_gui_user,
            create_fn=_create_gui_user,
            update_fn=_update_gui_user,
            delete_fn=_delete_gui_user,
        ),
    ]
    return {spec.key: spec for spec in specs}


def _sign(settings: MasterGuiSettings, value: str) -> str:
    import hashlib

    return hmac.new(settings.session_secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def _session_value(settings: MasterGuiSettings, username: str) -> str:
    expires = int((datetime.now(timezone.utc) + timedelta(seconds=_SESSION_MAX_AGE_SECONDS)).timestamp())
    payload = json.dumps({"u": username, "e": expires}, separators=(",", ":"))
    return f"{payload}.{_sign(settings, payload)}"


def _read_session(settings: MasterGuiSettings, request: Request) -> str | None:
    raw = request.cookies.get(_SESSION_COOKIE)
    if not raw or "." not in raw:
        return None
    payload, signature = raw.rsplit(".", 1)
    if not hmac.compare_digest(signature, _sign(settings, payload)):
        return None
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if int(data.get("e") or 0) < int(datetime.now(timezone.utc).timestamp()):
        return None
    return str(data.get("u") or "")


def _credentials_valid(settings: MasterGuiSettings, username: str, password: str) -> bool:
    if username == settings.admin_username and hmac.compare_digest(
        hash_password(password), settings.admin_password_hash
    ):
        return True
    return _gui_user_valid(username, password)


def _require_session(settings: MasterGuiSettings, request: Request) -> str:
    username = _read_session(settings, request)
    if not username:
        raise HTTPException(status_code=401, detail="login required")
    return username


def _redirect_login(request: Request) -> RedirectResponse:
    root_path = request.scope.get("root_path") or ""
    return RedirectResponse(f"{root_path}/gui/login", status_code=303)


def _page(title: str, body: str, request: Request) -> HTMLResponse:
    root_path = request.scope.get("root_path") or ""
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg:#0d1218;
      --panel:#151c24;
      --panel-2:#111820;
      --line:#2a3745;
      --line-soft:#22303c;
      --text:#e8eef5;
      --muted:#94a6b8;
      --accent:#67b7ff;
      --accent-strong:#2f7fca;
      --danger:#a64040;
      --field:#0f151b;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; background:var(--bg); color:var(--text); }}
    header {{ border-bottom:1px solid var(--line); background:#111922; }}
    .topbar {{ width:min(1600px, calc(100vw - 32px)); margin:0 auto; display:flex; align-items:center; justify-content:space-between; gap:20px; padding:18px 0; }}
    .brand {{ display:flex; flex-direction:column; gap:3px; }}
    .brand strong {{ font-size:1.06rem; }}
    .brand span {{ color:var(--muted); font-size:.86rem; }}
    main {{ padding:24px 0 32px; width:min(1600px, calc(100vw - 32px)); margin:0 auto; }}
    h1 {{ margin:0 0 12px; font-size:1.35rem; letter-spacing:0; }}
    h2 {{ margin:0; font-size:1rem; }}
    p {{ line-height:1.5; }}
    a {{ color:var(--accent); text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .card {{ border:1px solid var(--line); border-radius:8px; padding:18px; background:var(--panel); margin-bottom:16px; }}
    .card-head {{ display:flex; align-items:flex-start; justify-content:space-between; gap:18px; margin-bottom:14px; }}
    .card-subtitle {{ color:var(--muted); margin:0; }}
    .collection-grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(230px, 1fr)); gap:12px; margin-top:12px; }}
    .collection-tile {{ display:block; padding:15px; border:1px solid var(--line); border-radius:8px; background:var(--panel-2); color:var(--text); }}
    .collection-tile:hover {{ text-decoration:none; border-color:#3c88c8; }}
    .collection-tile span {{ display:block; color:var(--muted); font-size:.84rem; margin-top:5px; }}
    .grid-toolbar {{ display:flex; flex-wrap:wrap; gap:12px; align-items:center; justify-content:space-between; margin:12px 0; }}
    .grid-actions {{ display:flex; flex-wrap:wrap; gap:8px; }}
    .button-link, button {{ font:inherit; display:inline-flex; align-items:center; justify-content:center; min-height:36px; padding:8px 12px; border-radius:6px; border:1px solid var(--line); background:var(--accent-strong); color:white; cursor:pointer; text-decoration:none; }}
    .button-link.secondary {{ background:var(--panel-2); color:var(--text); }}
    .button-link:hover {{ text-decoration:none; border-color:#3c88c8; }}
    .grid-search {{ max-width:420px; min-width:min(100%, 260px); }}
    .table-wrap {{ overflow-x:auto; border:1px solid var(--line); border-radius:8px; background:var(--panel); }}
    table {{ width:100%; border-collapse:separate; border-spacing:0; min-width:900px; }}
    .nested-edit-table {{ min-width:760px; }}
    .nested-edit-table input[type=text] {{ min-width:120px; }}
    th, td {{ padding:0 12px; border-bottom:1px solid var(--line-soft); text-align:left; vertical-align:middle; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:320px; height:42px; }}
    th {{ color:var(--muted); font-weight:700; font-size:.78rem; text-transform:uppercase; letter-spacing:.04em; position:sticky; top:0; background:var(--panel-2); z-index:1; user-select:none; height:38px; }}
    tbody tr {{ height:42px; cursor:pointer; }}
    tbody tr:hover {{ background:rgba(103,183,255,.06); }}
    th.sortable {{ cursor:pointer; }}
    th.sortable::after {{ content:""; display:inline-block; margin-left:6px; color:var(--accent); }}
    th.sortable[data-dir="asc"]::after {{ content:"^"; }}
    th.sortable[data-dir="desc"]::after {{ content:"v"; }}
    tr.hidden {{ display:none; }}
    .record-cell {{ white-space:nowrap; cursor:default; }}
    .row-edit-link {{ min-height:28px; padding:4px 10px; }}
    .empty-row td {{ color:var(--muted); text-align:center; padding:22px; white-space:normal; }}
    .form-grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:12px 16px; }}
    .field {{ min-width:0; }}
    input[type=text], input[type=password], input[type=file], textarea, select {{ font:inherit; padding:9px 10px; border-radius:6px; border:1px solid #405160; background:var(--field); color:var(--text); width:100%; }}
    input:focus, textarea:focus, select:focus {{ outline:2px solid rgba(103,183,255,.35); border-color:var(--accent); }}
    select:disabled {{ color:#74808d; background:#141a20; cursor:not-allowed; }}
    .back-link {{ margin:0 0 14px; }}
    .back-link a {{ color:var(--muted); font-size:.9rem; }}
    .brand-link {{ color:inherit; text-decoration:none; }}
    .brand-link:hover {{ text-decoration:none; opacity:.85; }}
    .fk-combo {{ position:relative; }}
    .fk-combo-list {{ position:absolute; z-index:5; top:calc(100% + 2px); left:0; right:0; max-height:280px; overflow:auto; background:var(--panel-2); border:1px solid var(--line); border-radius:6px; box-shadow:0 8px 24px rgba(0,0,0,.35); }}
    .fk-combo-option {{ padding:8px 10px; cursor:pointer; font-size:.92rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
    .fk-combo-option:hover, .fk-combo-option.active {{ background:rgba(103,183,255,.12); }}
    label {{ display:block; margin:0 0 5px; color:var(--muted); font-size:.88rem; }}
    .compact-check {{ display:inline-flex; align-items:center; gap:6px; margin:0; color:var(--text); white-space:nowrap; }}
    .form-actions {{ margin-top:16px; display:flex; gap:10px; align-items:center; flex-wrap:wrap; }}
    .danger {{ background:var(--danger); }}
    .muted {{ color:var(--muted); }}
    dialog {{ width:min(440px, calc(100vw - 32px)); border:1px solid var(--line); border-radius:8px; padding:0; background:var(--panel); color:var(--text); }}
    dialog::backdrop {{ background:rgba(0,0,0,.55); }}
    .confirm-box {{ padding:18px; }}
    .confirm-box p {{ color:var(--muted); }}
    .confirm-actions {{ display:flex; gap:10px; justify-content:flex-end; margin-top:18px; }}
    nav {{ display:flex; gap:8px; align-items:center; }}
    nav a {{ color:var(--text); padding:8px 10px; border:1px solid transparent; border-radius:6px; }}
    nav a:hover {{ text-decoration:none; border-color:var(--line); background:var(--panel); }}
    form.inline {{ display:inline; }}
    @media (max-width: 720px) {{
      .topbar, .card-head {{ flex-direction:column; align-items:flex-start; }}
      main, .topbar {{ width:min(100vw - 20px, 1600px); }}
      .grid-search {{ max-width:none; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="topbar">
    <div class="brand"><a class="brand-link" href="{root_path}/gui"><strong>SARApp Central Master Database</strong></a><span>Agency-wide catalog console</span></div>
    <nav><a href="{root_path}/gui">Collections</a><a href="{root_path}/gui/logout">Logout</a></nav>
    </div>
  </header>
  <main>{body}</main>
<dialog id="confirm-dialog">
  <div class="confirm-box">
    <h2 id="confirm-title">Are you sure?</h2>
    <p id="confirm-message">This action cannot be undone.</p>
    <div class="confirm-actions">
      <button type="button" class="button-link secondary" id="confirm-cancel">Cancel</button>
      <button type="button" class="danger" id="confirm-accept">Delete</button>
    </div>
  </div>
</dialog>
<script>
(function() {{
  const confirmDialog = document.getElementById("confirm-dialog");
  const confirmTitle = document.getElementById("confirm-title");
  const confirmMessage = document.getElementById("confirm-message");
  const confirmCancel = document.getElementById("confirm-cancel");
  const confirmAccept = document.getElementById("confirm-accept");
  let pendingForm = null;

  function closeConfirm() {{
    pendingForm = null;
    if (confirmDialog && confirmDialog.open) confirmDialog.close();
  }}

  if (confirmCancel) confirmCancel.addEventListener("click", closeConfirm);
  if (confirmAccept) confirmAccept.addEventListener("click", () => {{
    const form = pendingForm;
    pendingForm = null;
    if (confirmDialog && confirmDialog.open) confirmDialog.close();
    if (form) form.submit();
  }});

  document.querySelectorAll("form[data-confirm]").forEach((form) => {{
    form.addEventListener("submit", (event) => {{
      if (form.dataset.confirmed === "1") return;
      event.preventDefault();
      pendingForm = form;
      if (confirmTitle) confirmTitle.textContent = form.dataset.confirmTitle || "Are you sure?";
      if (confirmMessage) confirmMessage.textContent = form.dataset.confirm || "This action cannot be undone.";
      if (confirmAccept) confirmAccept.textContent = form.dataset.confirmAction || "Delete";
      if (confirmDialog && typeof confirmDialog.showModal === "function") {{
        confirmDialog.showModal();
      }} else if (window.confirm(form.dataset.confirm || "This action cannot be undone.")) {{
        form.dataset.confirmed = "1";
        form.submit();
      }}
    }});
  }});

  function cellText(row, index) {{
    const cell = row.children[index];
    return cell ? cell.textContent.trim().toLowerCase() : "";
  }}

  document.querySelectorAll("[data-grid-search]").forEach((input) => {{
    const table = document.getElementById(input.dataset.gridSearch);
    if (!table) return;
    const rows = Array.from(table.querySelectorAll("tbody tr[data-row]"));
    const empty = table.querySelector("tbody tr.empty-row");
    input.addEventListener("input", () => {{
      const needle = input.value.trim().toLowerCase();
      let visible = 0;
      rows.forEach((row) => {{
        const match = !needle || row.textContent.toLowerCase().includes(needle);
        row.classList.toggle("hidden", !match);
        if (match) visible += 1;
      }});
      if (empty) empty.classList.toggle("hidden", visible !== 0);
    }});
  }});

  document.querySelectorAll("th.sortable").forEach((header) => {{
    header.addEventListener("click", () => {{
      const table = header.closest("table");
      const tbody = table ? table.querySelector("tbody") : null;
      if (!tbody) return;
      const index = Array.from(header.parentElement.children).indexOf(header);
      const dir = header.dataset.dir === "asc" ? "desc" : "asc";
      table.querySelectorAll("th.sortable").forEach((h) => delete h.dataset.dir);
      header.dataset.dir = dir;
      const rows = Array.from(tbody.querySelectorAll("tr[data-row]"));
      rows.sort((a, b) => {{
        const av = cellText(a, index);
        const bv = cellText(b, index);
        const an = Number(av);
        const bn = Number(bv);
        const cmp = !Number.isNaN(an) && !Number.isNaN(bn)
          ? an - bn
          : av.localeCompare(bv, undefined, {{ numeric:true, sensitivity:"base" }});
        return dir === "asc" ? cmp : -cmp;
      }});
      rows.forEach((row) => tbody.appendChild(row));
      const empty = tbody.querySelector("tr.empty-row");
      if (empty) tbody.appendChild(empty);
    }});
  }});

  document.querySelectorAll("tbody tr[data-row-href]").forEach((row) => {{
    row.addEventListener("dblclick", (event) => {{
      if (event.target.closest("a, button, input, textarea, select")) return;
      window.location.href = row.dataset.rowHref;
    }});
  }});

  // Searchable combobox for foreign-key pickers (organization/type/rank-
  // structure/home-unit selects) — a plain <select> with 150-200 options is
  // unusable, so this renders a text input + filtered dropdown list backed
  // by a JSON options array, with the real value kept in a hidden input.
  const fkCombos = new Map();

  function initFkCombo(combo) {{
    const hidden = combo.querySelector(".fk-combo-value");
    const input = combo.querySelector(".fk-combo-input");
    const list = combo.querySelector(".fk-combo-list");
    const dataEl = combo.querySelector(".fk-combo-options");
    let options = [];
    try {{
      options = JSON.parse((dataEl && dataEl.textContent) || "[]");
    }} catch (err) {{
      options = [];
    }}

    function render(filterText) {{
      const needle = filterText.trim().toLowerCase();
      const matches = (needle ? options.filter((o) => o.label.toLowerCase().includes(needle)) : options).slice(0, 50);
      list.innerHTML = "";
      matches.forEach((opt) => {{
        const row = document.createElement("div");
        row.className = "fk-combo-option";
        row.textContent = opt.label;
        row.addEventListener("mousedown", (event) => {{
          event.preventDefault();
          hidden.value = opt.id;
          input.value = opt.label;
          list.hidden = true;
          hidden.dispatchEvent(new Event("fkcombo:change", {{ bubbles: true }}));
        }});
        list.appendChild(row);
      }});
      list.hidden = matches.length === 0;
    }}

    input.addEventListener("focus", () => {{ if (!input.disabled) render(""); }});
    input.addEventListener("input", () => {{
      hidden.value = "";
      render(input.value);
    }});
    input.addEventListener("blur", () => {{
      window.setTimeout(() => {{ list.hidden = true; }}, 150);
    }});

    const entry = {{
      hidden: hidden,
      input: input,
      setOptions(nextOptions) {{
        options = nextOptions;
      }},
    }};
    fkCombos.set(hidden.name, entry);
    return entry;
  }}

  document.querySelectorAll("[data-fk-combo]").forEach(initFkCombo);

  document.querySelectorAll("[data-combo-depends]").forEach((combo) => {{
    const dependsName = combo.dataset.comboDepends;
    const controller = fkCombos.get(dependsName);
    const hidden = combo.querySelector(".fk-combo-value");
    const dependent = fkCombos.get(hidden.name);
    const mapScript = document.querySelector(`[data-combo-depmap-for="${{dependsName}}"]`);
    if (!controller || !dependent || !mapScript) return;
    let depMap = {{}};
    try {{
      depMap = JSON.parse(mapScript.textContent || "{{}}");
    }} catch (err) {{
      depMap = {{}};
    }}

    function refresh() {{
      const options = (depMap[controller.hidden.value] || []).map((value) => ({{ id: value, label: value }}));
      dependent.setOptions(options);
      dependent.input.disabled = options.length === 0;
      if (!options.some((opt) => opt.id === dependent.hidden.value)) {{
        dependent.hidden.value = "";
        dependent.input.value = "";
      }}
    }}
    controller.hidden.addEventListener("fkcombo:change", refresh);
    refresh();
  }});
}})();
</script>
</body>
</html>"""
    return HTMLResponse(html)


def _back_link(href: str, label: str) -> str:
    return f'<p class="back-link"><a href="{href}">&larr; {escape(label)}</a></p>'


def _combo_html(
    name: str,
    value: Any,
    options: list[tuple[str, str]],
    *,
    placeholder: str = "Type to search…",
    disabled: bool = False,
    depends_on: str | None = None,
) -> str:
    current = str(value) if value not in (None, "") else ""
    current_label = next((label for opt_id, label in options if opt_id == current), current)
    options_json = json.dumps(
        [{"id": opt_id, "label": label} for opt_id, label in options], separators=(",", ":")
    ).replace("</", "<\\/")
    depends_attr = f' data-combo-depends="{escape(depends_on)}"' if depends_on else ""
    disabled_attr = " disabled" if disabled else ""
    return (
        f'<div class="fk-combo" data-fk-combo="1"{depends_attr}>'
        f'<input type="hidden" name="{escape(name)}" value="{escape(current)}" class="fk-combo-value">'
        f'<input type="text" class="fk-combo-input" value="{escape(current_label)}" '
        f'placeholder="{escape(placeholder)}" autocomplete="off"{disabled_attr}>'
        f'<div class="fk-combo-list" hidden></div>'
        f'<script type="application/json" class="fk-combo-options">{options_json}</script>'
        f"</div>"
    )


def _field_input_html(
    field: FieldSpec,
    value: Any,
    *,
    combo_options: dict[str, list[tuple[str, str]]] | None = None,
    combo_depends: dict[str, str] | None = None,
) -> str:
    safe_value = escape(str(value)) if value is not None else ""
    if field.input_type == "checkbox":
        checked = "checked" if str(value).strip().lower() in {"1", "true", "yes", "y", "on"} else ""
        return f'<input type="checkbox" name="{escape(field.name)}" {checked}>'
    if field.input_type in ("select_fk", "select"):
        options = list((combo_options or {}).get(field.name, []))
        current = str(value) if value not in (None, "") else ""
        if field.input_type == "select" and current and current not in {opt_id for opt_id, _ in options}:
            options = [(current, current)] + options
        disabled = field.input_type == "select" and field.name == "rank" and not options and not current
        return _combo_html(
            field.name, value, options, disabled=disabled, depends_on=(combo_depends or {}).get(field.name)
        )
    if field.input_type == "textarea":
        return f'<textarea name="{escape(field.name)}" rows="3">{safe_value}</textarea>'
    return f'<input type="text" name="{escape(field.name)}" value="{safe_value}">'


def _cell_html(value: Any) -> str:
    text = _stringify(value)
    if len(text) > 180:
        text = f"{text[:177]}..."
    return escape(text)


def _form_html(spec: CollectionSpec, doc: dict[str, Any], *, action: str, submit_label: str) -> str:
    combo_options: dict[str, list[tuple[str, str]]] = {}
    combo_depends: dict[str, str] = {}
    depmap_scripts = ""
    if spec.key == "personnel":
        org_rank_options = _personnel_org_rank_options()
        organization = str(doc.get("home_unit") or "").strip()
        combo_options["home_unit"] = org_rank_options["organization_options"]
        combo_options["rank"] = [(r, r) for r in org_rank_options["rank_by_org"].get(organization, [])]
        combo_depends["rank"] = "home_unit"
        depmap_json = json.dumps(org_rank_options["rank_by_org"], separators=(",", ":")).replace("</", "<\\/")
        depmap_scripts += f'<script type="application/json" data-combo-depmap-for="home_unit">{depmap_json}</script>'
    if spec.key == "organizations":
        from sarapp_db.api.routers import organizations as organizations_router

        self_id = doc.get("int_id")
        orgs = [
            (
                str(o.get("int_id")),
                f"{o.get('short_name')} - {o.get('name')}" if o.get("short_name") else str(o.get("name")),
            )
            for o in organizations_router.list_organizations(search="")
            if o.get("name") and o.get("int_id") != self_id
        ]
        org_types = [
            (str(t.get("int_id")), str(t.get("name")))
            for t in organizations_router.list_org_types(search="")
            if t.get("name")
        ]
        rank_structures = [
            (str(r.get("int_id")), str(r.get("name")))
            for r in organizations_router.list_rank_structures(search="")
            if r.get("name")
        ]
        combo_options["parent_organization_id"] = sorted(orgs, key=lambda t: t[1].lower())
        combo_options["organization_type_id"] = sorted(org_types, key=lambda t: t[1].lower())
        combo_options["default_rank_structure_id"] = sorted(rank_structures, key=lambda t: t[1].lower())

    rows = []
    for field in spec.fields:
        rows.append(
            f'<div class="field"><label for="{escape(field.name)}">{escape(field.label)}</label>'
            f"{_field_input_html(field, doc.get(field.name), combo_options=combo_options, combo_depends=combo_depends)}</div>"
        )
    return f"""<form method="post" action="{action}">{depmap_scripts}<div class="form-grid">{''.join(rows)}</div>
  <div class="form-actions"><button type="submit">{escape(submit_label)}</button></div>
</form>"""


def _rank_structure_ranks_html(structure_id: int, root_path: str) -> str:
    from sarapp_db.api.routers import organizations as organizations_router

    ranks = organizations_router.list_ranks(structure_id=structure_id, search="")
    editable_rows = list(ranks) + [{} for _ in range(3)]
    row_html: list[str] = []
    for index, rank in enumerate(editable_rows):
        rank_id = rank.get("int_id") or rank.get("id") or ""
        active = int(rank.get("is_active", 1)) if rank else 1
        delete_cell = (
            f'<label class="compact-check"><input type="checkbox" name="delete_{index}"> Delete</label>'
            if rank_id
            else ""
        )
        row_html.append(
            "<tr>"
            f'<td><input type="hidden" name="rank_id_{index}" value="{escape(str(rank_id))}">'
            f'<input type="text" name="rank_code_{index}" value="{escape(str(rank.get("rank_code") or ""))}"></td>'
            f'<td><input type="text" name="rank_name_{index}" value="{escape(str(rank.get("rank_name") or rank.get("name") or ""))}"></td>'
            f'<td><input type="text" name="short_display_{index}" value="{escape(str(rank.get("short_display") or ""))}"></td>'
            f'<td><input type="text" name="sort_order_{index}" value="{escape(str(rank.get("sort_order") or rank.get("rank_order") or 0 if rank else ""))}"></td>'
            f'<td><label class="compact-check"><input type="checkbox" name="is_active_{index}" {"checked" if active else ""}> Active</label></td>'
            f"<td>{delete_cell}</td>"
            "</tr>"
        )
    return f"""<section class="card">
  <div class="card-head"><div><h1>Ranks In This Structure</h1>
  <p class="card-subtitle">Edit the rank rows for this template here. Blank rows are ignored.</p></div></div>
  <form method="post" action="{root_path}/gui/rank-structures/{structure_id}/ranks">
    <input type="hidden" name="row_count" value="{len(editable_rows)}">
    <div class="table-wrap">
      <table class="nested-edit-table">
        <thead><tr><th>Rank Code</th><th>Rank Name</th><th>Short Display</th><th>Sort Order</th><th>Active</th><th>Delete</th></tr></thead>
        <tbody>{''.join(row_html)}</tbody>
      </table>
    </div>
    <div class="form-actions"><button type="submit">Save Ranks</button></div>
  </form>
</section>"""


def _parse_rank_rows(structure_id: int, form: dict[str, Any]) -> None:
    from sarapp_db.api.routers import organizations as organizations_router

    try:
        row_count = int(form.get("row_count") or 0)
    except (TypeError, ValueError):
        row_count = 0
    for index in range(row_count):
        rank_id_text = str(form.get(f"rank_id_{index}") or "").strip()
        rank_code = str(form.get(f"rank_code_{index}") or "").strip()
        rank_name = str(form.get(f"rank_name_{index}") or "").strip()
        short_display = str(form.get(f"short_display_{index}") or "").strip()
        sort_order_text = str(form.get(f"sort_order_{index}") or "").strip()
        try:
            sort_order = int(sort_order_text) if sort_order_text else 0
        except ValueError:
            sort_order = 0
        is_active = 1 if f"is_active_{index}" in form else 0
        delete_requested = f"delete_{index}" in form

        if rank_id_text:
            rank_id = int(rank_id_text)
            if delete_requested:
                organizations_router.delete_rank(rank_id)
                continue
            organizations_router.update_rank(
                rank_id,
                {
                    "rank_code": rank_code,
                    "rank_name": rank_name,
                    "short_display": short_display,
                    "sort_order": sort_order,
                    "is_active": is_active,
                },
            )
            continue

        if rank_code or rank_name or short_display:
            organizations_router.create_rank(
                {
                    "rank_structure_id": structure_id,
                    "rank_code": rank_code,
                    "rank_name": rank_name,
                    "short_display": short_display,
                    "sort_order": sort_order,
                    "is_active": is_active,
                }
            )


def _parse_form_body(spec: CollectionSpec, form: dict[str, str]) -> dict[str, Any]:
    if spec.form_payload_fn is not None:
        return spec.form_payload_fn(form)
    body: dict[str, Any] = {}
    for field in spec.fields:
        if field.input_type == "checkbox":
            value = field.name in form
            body[field.name] = int(value) if field.value_type == "int" else value
        elif field.value_type == "int":
            raw = str(form.get(field.name, "")).strip()
            body[field.name] = int(raw) if raw else None
        elif field.value_type == "float":
            raw = str(form.get(field.name, "")).strip()
            body[field.name] = float(raw) if raw else None
        else:
            body[field.name] = form.get(field.name, "")
    return body


def _coerce_import_payload(spec: CollectionSpec, row: dict[str, str]) -> dict[str, Any]:
    if spec.import_payload_fn is not None:
        return spec.import_payload_fn(row)
    return _coerce_fields_payload(spec.fields, row, keys=_field_keys(spec))

def _coerce_fields_payload(
    fields: list[FieldSpec],
    row: dict[str, str],
    *,
    keys: list[str] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    field_by_name = {field.name: field for field in fields}
    for key in keys or [field.name for field in fields]:
        field = field_by_name.get(key)
        raw = str(row.get(key, "")).strip()
        if not raw:
            continue
        if field and field.input_type == "checkbox":
            body[key] = 1 if raw.lower() in {"1", "true", "yes", "y", "on"} else 0
        elif field and field.value_type == "int":
            body[key] = int(raw)
        elif field and field.value_type == "float":
            body[key] = float(raw)
        else:
            body[key] = raw
    return body


def _form_doc(spec: CollectionSpec, doc: dict[str, Any]) -> dict[str, Any]:
    if spec.form_row_fn is not None:
        return spec.form_row_fn(doc)
    return doc


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def _export_bytes(spec: CollectionSpec, rows: list[dict[str, Any]], fmt: str) -> bytes:
    """Same column shape as `utils/edit_window_kit.write_export_file`
    (desktop) — headers are labels, one row per record — reimplemented
    here instead of imported, since that module pulls in PySide6 and this
    process has no Qt dependency."""
    field_keys = _field_keys(spec)
    field_labels = _field_labels(spec)
    export_rows = [spec.export_row_fn(row) if spec.export_row_fn else row for row in rows]
    headers = [field_labels.get(key, key.title()) for key in field_keys]
    if fmt == "xlsx":
        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.append(headers)
        for row in export_rows:
            sheet.append([_stringify(row.get(key)) for key in field_keys])
        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in export_rows:
        writer.writerow([_stringify(row.get(key)) for key in field_keys])
    return buffer.getvalue().encode("utf-8")


def _read_import_rows(spec: CollectionSpec, filename: str, data: bytes) -> list[dict[str, str]]:
    """Parse an uploaded CSV/XLSX export back into field-keyed row dicts.
    Matches each column header against a field's label or key
    (case-insensitive) — the same labels `_export_bytes` writes, so a file
    round-trips through either this page or the desktop panel's own
    Export/Import."""
    field_keys = _field_keys(spec)
    label_by_key = _field_labels(spec)
    key_by_header = {label.strip().lower(): key for key, label in label_by_key.items()}
    key_by_header.update({key.strip().lower(): key for key in field_keys})

    def _row_from_headers(headers: list[str], values: list[Any]) -> dict[str, str]:
        row: dict[str, str] = {}
        for header, value in zip(headers, values):
            key = key_by_header.get(str(header or "").strip().lower())
            if key:
                row[key] = _stringify(value)
        return row

    if filename.lower().endswith(".xlsx"):
        from openpyxl import load_workbook

        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        sheet = workbook.active
        rows_iter = sheet.iter_rows(values_only=True)
        headers = [str(h or "") for h in next(rows_iter, [])]
        return [_row_from_headers(headers, list(values)) for values in rows_iter]

    text = data.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return []
    headers = rows[0]
    return [_row_from_headers(headers, values) for values in rows[1:]]


def create_master_gui_router() -> APIRouter:
    """Build the `/gui/...` router. Call once per app; routes read live
    settings/specs on each request rather than freezing them at import."""
    router = APIRouter()
    settings = load_settings()
    specs = _build_collection_specs()

    @router.get("/gui/login", response_class=HTMLResponse)
    def login_page(request: Request) -> HTMLResponse:
        body = """
<div class="card" style="max-width:440px;margin:64px auto;">
  <h1>Central Master Database</h1>
  <p class="muted">Sign in to manage master catalog records and console users.</p>
  <form method="post">
    <div class="field"><label>Username</label><input type="text" name="username" autocomplete="username"></div>
    <div class="field" style="margin-top:12px;"><label>Password</label><input type="password" name="password" autocomplete="current-password"></div>
    <div class="form-actions"><button type="submit">Sign in</button></div>
  </form>
</div>"""
        return _page("Login", body, request)

    @router.post("/gui/login")
    def login(request: Request, username: str = Form(...), password: str = Form(...)) -> RedirectResponse:
        if not _credentials_valid(settings, username, password):
            return _redirect_login(request)
        response = RedirectResponse(f"{request.scope.get('root_path') or ''}/gui", status_code=303)
        response.set_cookie(
            _SESSION_COOKIE,
            _session_value(settings, username),
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=_SESSION_MAX_AGE_SECONDS,
        )
        return response

    @router.get("/gui/logout")
    def logout(request: Request) -> RedirectResponse:
        response = _redirect_login(request)
        response.delete_cookie(_SESSION_COOKIE)
        return response

    @router.get("/gui", response_class=HTMLResponse, response_model=None)
    def index(request: Request) -> Response:
        try:
            _require_session(settings, request)
        except HTTPException:
            return _redirect_login(request)
        root_path = request.scope.get("root_path") or ""
        visible_specs = [spec for spec in specs.values() if spec.key != "ranks"]
        items = "".join(
            f'<a class="collection-tile" href="{root_path}/gui/{escape(spec.key)}">{escape(spec.title)}'
            f'<span>{len(spec.fields)} editable fields</span></a>'
            for spec in visible_specs
        )
        body = f"""<section class="card"><div class="card-head"><div><h1>Master Catalog Collections</h1>
  <p class="card-subtitle">Central source for personnel, equipment, vehicles, organizations, ranks, and console access.</p></div></div>
  <div class="collection-grid">{items}</div>
</section>"""
        return _page("Collections", body, request)

    @router.get("/gui/{collection_key}", response_class=HTMLResponse, response_model=None)
    def list_collection(request: Request, collection_key: str) -> Response:
        try:
            _require_session(settings, request)
        except HTTPException:
            return _redirect_login(request)
        spec = specs.get(collection_key)
        if spec is None:
            raise HTTPException(status_code=404, detail="Unknown collection")
        root_path = request.scope.get("root_path") or ""

        docs = spec.list_fn()
        table_id = f"grid-{collection_key}"
        field_by_name = {f.name: f for f in spec.fields}
        shown_names = spec.list_fields or [f.name for f in spec.fields]
        shown_fields = [field_by_name[name] for name in shown_names if name in field_by_name and name != "sort_order"]
        header_cells = "".join(f'<th class="sortable">{escape(f.label)}</th>' for f in shown_fields)
        list_cell_fn = spec.list_cell_fn
        if collection_key == "personnel":
            from sarapp_db.api.routers import organizations as organizations_router

            short_by_org_name = {
                str(o.get("name") or ""): str(o.get("short_name") or "")
                for o in organizations_router.list_organizations(search="")
            }

            def list_cell_fn(row_doc: dict[str, Any], field_name: str, _short_by_name=short_by_org_name) -> Any:
                if field_name == "home_unit":
                    name = str(row_doc.get("home_unit") or "")
                    short = _short_by_name.get(name, "")
                    return f"{short} - {name}" if short and name else name
                return row_doc.get(field_name)

        rows = []
        for doc in docs:
            record_id = doc.get(spec.record_field)
            display_doc = _form_doc(spec, doc)
            cells = "".join(
                f"<td>{_cell_html(list_cell_fn(display_doc, f.name) if list_cell_fn else display_doc.get(f.name, ''))}</td>"
                for f in shown_fields
            )
            row_href = f"{root_path}/gui/{collection_key}/{record_id}"
            rows.append(
                f'<tr data-row data-row-href="{row_href}"><td class="record-cell">'
                f'<a class="button-link secondary row-edit-link" href="{row_href}">Edit</a></td>{cells}</tr>'
            )
        rows.append(
            f'<tr class="empty-row {"hidden" if docs else ""}"><td colspan="{len(shown_fields) + 1}">'
            "No matching records.</td></tr>"
        )
        body = f"""{_back_link(f"{root_path}/gui", "Back to Collections")}<section class="card"><div class="card-head"><div><h1>{escape(spec.title)}</h1>
  <p class="card-subtitle">{len(docs)} record{"s" if len(docs) != 1 else ""}</p></div></div>
  <div class="grid-toolbar">
    <div class="grid-actions">
      <a class="button-link" href="{root_path}/gui/{collection_key}/new">New {escape(spec.title)}</a>
      <a class="button-link secondary" href="{root_path}/gui/{collection_key}/export?format=csv">Export CSV</a>
      <a class="button-link secondary" href="{root_path}/gui/{collection_key}/export?format=xlsx">Export XLSX</a>
      <a class="button-link secondary" href="{root_path}/gui/{collection_key}/import">Import</a>
      {f'''<a class="button-link secondary" href="{root_path}/gui/ranks/import">Import Ranks</a>''' if collection_key == "rank-structures" else ""}
      {f'''<form class="inline" method="post" action="{root_path}/gui/{collection_key}/delete-all" data-confirm-title="Delete all {escape(spec.title)}?" data-confirm="This will permanently delete every record currently in {escape(spec.title)}. This cannot be undone." data-confirm-action="Delete all"><button type="submit" class="danger">Delete All</button></form>''' if spec.delete_fn is not None else ""}
    </div>
    <input class="grid-search" type="text" data-grid-search="{table_id}" placeholder="Search this table">
  </div>
  <div class="table-wrap">
    <table id="{table_id}">
      <thead><tr><th>Edit</th>{header_cells}</tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </div>
</section>"""
        return _page(spec.title, body, request)

    @router.get("/gui/{collection_key}/new", response_class=HTMLResponse, response_model=None)
    def new_form(request: Request, collection_key: str) -> Response:
        try:
            _require_session(settings, request)
        except HTTPException:
            return _redirect_login(request)
        spec = specs.get(collection_key)
        if spec is None:
            raise HTTPException(status_code=404, detail="Unknown collection")
        root_path = request.scope.get("root_path") or ""
        form = _form_html(spec, {}, action=f"{root_path}/gui/{collection_key}/new", submit_label="Create")
        back = _back_link(f"{root_path}/gui/{collection_key}", f"Back to {spec.title}")
        body = f'{back}<section class="card"><h1>New {escape(spec.title)}</h1>{form}</section>'
        return _page(f"New {spec.title}", body, request)

    @router.post("/gui/{collection_key}/new")
    async def create_record(request: Request, collection_key: str) -> Response:
        try:
            _require_session(settings, request)
        except HTTPException:
            return _redirect_login(request)
        spec = specs.get(collection_key)
        if spec is None:
            raise HTTPException(status_code=404, detail="Unknown collection")
        form = dict((await request.form()).items())
        body = _parse_form_body(spec, form)
        spec.create_fn(body)
        root_path = request.scope.get("root_path") or ""
        return RedirectResponse(f"{root_path}/gui/{collection_key}", status_code=303)

    @router.get("/gui/{collection_key}/export", response_model=None)
    def export_collection(request: Request, collection_key: str, format: str = "csv") -> Response:
        try:
            _require_session(settings, request)
        except HTTPException:
            return _redirect_login(request)
        spec = specs.get(collection_key)
        if spec is None:
            raise HTTPException(status_code=404, detail="Unknown collection")
        fmt = "xlsx" if format == "xlsx" else "csv"
        data = _export_bytes(spec, spec.list_fn(), fmt)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if fmt == "xlsx" else "text/csv"
        filename = f"{collection_key}.{fmt}"
        return Response(
            content=data,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.get("/gui/{collection_key}/import", response_class=HTMLResponse, response_model=None)
    def import_form(request: Request, collection_key: str) -> Response:
        try:
            _require_session(settings, request)
        except HTTPException:
            return _redirect_login(request)
        spec = specs.get(collection_key)
        if spec is None:
            raise HTTPException(status_code=404, detail="Unknown collection")
        root_path = request.scope.get("root_path") or ""
        back = _back_link(f"{root_path}/gui/{collection_key}", f"Back to {spec.title}")
        body = f"""{back}<section class="card"><h1>Import {escape(spec.title)}</h1>
  <p class="muted">Upload a CSV or XLSX file exported from this page or the desktop Edit-menu panel — same columns, matched by header.</p>
  <form method="post" enctype="multipart/form-data" action="{root_path}/gui/{collection_key}/import">
    <input type="file" name="file" accept=".csv,.xlsx" required>
    <div class="form-actions"><button type="submit">Import</button></div>
  </form>
</section>"""
        return _page(f"Import {spec.title}", body, request)

    @router.post("/gui/{collection_key}/import", response_class=HTMLResponse, response_model=None)
    async def import_collection(request: Request, collection_key: str, file: UploadFile = File(...)) -> Response:
        try:
            _require_session(settings, request)
        except HTTPException:
            return _redirect_login(request)
        spec = specs.get(collection_key)
        if spec is None:
            raise HTTPException(status_code=404, detail="Unknown collection")
        data = await file.read()
        rows = _read_import_rows(spec, file.filename or "", data)

        created = 0
        errors: list[str] = []
        for index, row in enumerate(rows, start=1):
            try:
                payload = _coerce_import_payload(spec, row)
                spec.create_fn(payload)
                created += 1
            except Exception as exc:  # noqa: BLE001 - one bad row must not abort the rest
                errors.append(f"Row {index}: {exc}")

        root_path = request.scope.get("root_path") or ""
        error_html = (
            "<ul>" + "".join(f"<li>{escape(e)}</li>" for e in errors) + "</ul>" if errors else ""
        )
        body = f"""<section class="card"><h1>Import Complete</h1>
  <p>{created} {escape(spec.title)} imported{f", {len(errors)} error(s)" if errors else ""}.</p>
  {error_html}
  <p><a class="button-link secondary" href="{root_path}/gui/{collection_key}">Back to {escape(spec.title)}</a></p>
</section>"""
        return _page("Import Complete", body, request)

    @router.post("/gui/{collection_key}/delete-all")
    def delete_all_records(request: Request, collection_key: str) -> Response:
        try:
            _require_session(settings, request)
        except HTTPException:
            return _redirect_login(request)
        spec = specs.get(collection_key)
        if spec is None:
            raise HTTPException(status_code=404, detail="Unknown collection")
        if spec.delete_fn is None:
            raise HTTPException(status_code=405, detail="Collection does not support delete")
        docs = spec.list_fn()
        for doc in docs:
            record_id = doc.get(spec.record_field)
            if record_id is not None:
                spec.delete_fn(int(record_id))
        root_path = request.scope.get("root_path") or ""
        return RedirectResponse(f"{root_path}/gui/{collection_key}", status_code=303)

    @router.get("/gui/{collection_key}/{record_id}", response_class=HTMLResponse, response_model=None)
    def edit_form(request: Request, collection_key: str, record_id: int) -> Response:
        try:
            _require_session(settings, request)
        except HTTPException:
            return _redirect_login(request)
        spec = specs.get(collection_key)
        if spec is None:
            raise HTTPException(status_code=404, detail="Unknown collection")
        doc = spec.get_fn(record_id)
        root_path = request.scope.get("root_path") or ""
        form = _form_html(
            spec, _form_doc(spec, doc), action=f"{root_path}/gui/{collection_key}/{record_id}", submit_label="Save"
        )
        delete_button = (
            f"""<form class="inline" method="post" action="{root_path}/gui/{collection_key}/{record_id}/delete" data-confirm-title="Delete {escape(spec.title)} {record_id}?" data-confirm="This will permanently delete this record. This cannot be undone." data-confirm-action="Delete">
  <button type="submit" class="danger">Delete</button>
</form>"""
            if spec.delete_fn is not None
            else ""
        )
        back = _back_link(f"{root_path}/gui/{collection_key}", f"Back to {spec.title}")
        body = f'{back}<section class="card"><h1>{escape(spec.title)} {record_id}</h1>{form}<div class="form-actions">{delete_button}</div></section>'
        if spec.key == "rank-structures":
            body += _rank_structure_ranks_html(record_id, root_path)
        return _page(f"Edit {spec.title}", body, request)

    @router.post("/gui/rank-structures/{record_id}/ranks")
    async def update_rank_structure_ranks(request: Request, record_id: int) -> Response:
        try:
            _require_session(settings, request)
        except HTTPException:
            return _redirect_login(request)
        form = dict((await request.form()).items())
        _parse_rank_rows(record_id, form)
        root_path = request.scope.get("root_path") or ""
        return RedirectResponse(f"{root_path}/gui/rank-structures/{record_id}", status_code=303)

    @router.post("/gui/{collection_key}/{record_id}")
    async def update_record(request: Request, collection_key: str, record_id: int) -> Response:
        try:
            _require_session(settings, request)
        except HTTPException:
            return _redirect_login(request)
        spec = specs.get(collection_key)
        if spec is None:
            raise HTTPException(status_code=404, detail="Unknown collection")
        form = dict((await request.form()).items())
        body = _parse_form_body(spec, form)
        spec.update_fn(record_id, body)
        root_path = request.scope.get("root_path") or ""
        return RedirectResponse(f"{root_path}/gui/{collection_key}/{record_id}", status_code=303)

    @router.post("/gui/{collection_key}/{record_id}/delete")
    def delete_record(request: Request, collection_key: str, record_id: int) -> Response:
        try:
            _require_session(settings, request)
        except HTTPException:
            return _redirect_login(request)
        spec = specs.get(collection_key)
        if spec is None or spec.delete_fn is None:
            raise HTTPException(status_code=404, detail="Unknown collection")
        spec.delete_fn(record_id)
        root_path = request.scope.get("root_path") or ""
        return RedirectResponse(f"{root_path}/gui/{collection_key}", status_code=303)

    return router
