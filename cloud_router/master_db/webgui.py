"""Browser-based CRUD GUI for the central master-catalog database.

No master-data-editing web GUI exists anywhere else in the product — today
master data is only edited through the desktop app's admin panels over
LAN/localhost (see `Design Documents/Instructions/cloud_router_architecture.md`
"Central Master Database"). The GUI exposes the flat master catalogs that
can be safely edited with catalog-aware controls; nested/versioned catalogs
stay out of this generic CRUD surface until they have purpose-built editors.

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
import re
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Any, Callable, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from master_db.config import MasterGuiSettings, hash_password, load_settings

_SESSION_COOKIE = "sarapp_central_master_session"
_SESSION_MAX_AGE_SECONDS = 12 * 60 * 60


@dataclass(frozen=True)
class FieldSpec:
    name: str
    label: str
    input_type: str = "text"  # "text" | "password" | "number" | "checkbox" | "textarea" | "list" | "select" | "select_fk" | "combo"
    value_type: str = "str"  # "str" | "int" | "float" | "bool"


@dataclass(frozen=True)
class CollectionSpec:
    key: str
    title: str
    record_field: str
    fields: list[FieldSpec]
    list_fn: Callable[[], list[dict[str, Any]]]
    get_fn: Callable[[Any], dict[str, Any]]
    create_fn: Callable[[dict[str, Any]], dict[str, Any]]
    update_fn: Callable[[Any, dict[str, Any]], dict[str, Any]]
    delete_fn: Optional[Callable[[Any], None]]
    record_id_type: str = "int"  # "int" | "str"
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
    # Field names (subset of `list_fields`/`fields`) that can be edited
    # in place in the list-table grid via double-click, instead of only
    # through the record's full edit page. None/empty disables inline
    # editing for this collection entirely (the grid row still
    # double-click-navigates to the edit page in that case).
    inline_edit_fields: Optional[list[str]] = None


def _field_keys(spec: CollectionSpec) -> list[str]:
    return spec.export_fields or [field.name for field in spec.fields]


def _field_labels(spec: CollectionSpec) -> dict[str, str]:
    labels = {field.name: field.label for field in spec.fields}
    labels.update(spec.export_field_labels)
    return labels


def _record_route_arg(spec: CollectionSpec, record_id: str) -> Any:
    if spec.record_id_type == "str":
        return record_id
    return int(record_id)


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


def _resource_type_create_payload(resource_type_body_cls: type, body: dict[str, Any]) -> Any:
    payload = {key: value for key, value in body.items() if value is not None}
    return resource_type_body_cls(**payload)


def _resource_type_update_payload(resource_type_body_cls: type, body: dict[str, Any]) -> Any:
    payload = {key: value for key, value in body.items() if value is not None}
    return resource_type_body_cls(**payload)


def _get_resource_capability(capability_id: int) -> dict[str, Any]:
    from sarapp_db.api.routers import resource_types as resource_types_router

    for row in resource_types_router.list_capabilities(include_inactive=True, category="All"):
        if row.get("id") == capability_id:
            return row
    raise HTTPException(status_code=404, detail="Capability not found")


def _save_resource_capability(capability_body_cls: type, body: dict[str, Any]) -> dict[str, Any]:
    payload = {key: value for key, value in body.items() if value is not None}
    return capability_body_cls(**payload)


def _create_resource_capability(body: dict[str, Any]) -> dict[str, Any]:
    from sarapp_db.api.routers import resource_types as resource_types_router

    return resource_types_router.save_capability(
        _save_resource_capability(resource_types_router.SaveCapabilityRequest, body)
    )


def _update_resource_capability(capability_id: int, body: dict[str, Any]) -> dict[str, Any]:
    from sarapp_db.api.routers import resource_types as resource_types_router

    payload = dict(body)
    payload["capability_id"] = str(capability_id)
    return resource_types_router.save_capability(
        _save_resource_capability(resource_types_router.SaveCapabilityRequest, payload)
    )


def _csv_to_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def _list_to_csv(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if str(item).strip())
    return str(value or "")


def _list_to_lines(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(str(item) for item in value if str(item).strip())
    return str(value or "")


def _lines_to_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [line.strip() for line in str(value or "").splitlines() if line.strip()]


def _slugify(value: Any) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return slug or "template"


def _hazard_form_row(doc: dict[str, Any]) -> dict[str, Any]:
    row = dict(doc)
    default_spe = row.get("default_spe") or {}
    row["default_spe_severity"] = default_spe.get("severity", 1)
    row["default_spe_probability"] = default_spe.get("probability", 1)
    row["default_spe_exposure"] = default_spe.get("exposure", 1)
    row["aliases"] = _list_to_csv(row.get("aliases"))
    row["controls"] = _list_to_csv(row.get("controls"))
    row["ppe"] = _list_to_csv(row.get("ppe"))
    return row


def _hazard_form_payload(hazard_body_cls: type, spe_input_cls: type, form: dict[str, Any]) -> Any:
    return hazard_body_cls(
        name=str(form.get("name") or ""),
        category=str(form.get("category") or "Other"),
        description=str(form.get("description") or ""),
        aliases=_csv_to_list(form.get("aliases")),
        controls=_csv_to_list(form.get("controls")),
        ppe=_csv_to_list(form.get("ppe")),
        standard_safety_language=str(form.get("standard_safety_language") or ""),
        default_spe=spe_input_cls(
            severity=int(form.get("default_spe_severity") or 1),
            probability=int(form.get("default_spe_probability") or 1),
            exposure=int(form.get("default_spe_exposure") or 1),
        ),
        active=bool(form.get("active")),
    )


def _template_form_row(doc: dict[str, Any]) -> dict[str, Any]:
    row = dict(doc)
    row["tags"] = _list_to_csv(row.get("tags"))
    return row


def _objective_template_payload(form: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": str(form.get("code") or "") or None,
        "title": str(form.get("title") or ""),
        "description": str(form.get("description") or ""),
        "default_section": str(form.get("default_section") or "") or None,
        "priority": str(form.get("priority") or "Normal"),
        "active": bool(form.get("active")),
        "tags": _csv_to_list(form.get("tags")),
    }


def _strategy_template_payload(form: dict[str, Any]) -> dict[str, Any]:
    objective_template_id: int | None
    raw_objective_id = str(form.get("objective_template_id") or "").strip()
    objective_template_id = int(raw_objective_id) if raw_objective_id else None
    return {
        "objective_template_id": objective_template_id,
        "title": str(form.get("title") or ""),
        "description": str(form.get("description") or ""),
        "assignment_kind": str(form.get("assignment_kind") or "Ground"),
        "branch": str(form.get("branch") or "") or None,
        "division_group": str(form.get("division_group") or "") or None,
        "priority": str(form.get("priority") or "Normal"),
        "active": bool(form.get("active")),
        "tags": _csv_to_list(form.get("tags")),
    }


_MEETING_TEMPLATE_LIST_FIELDS = {
    "agenda_sections",
    "required_attendee_roles",
    "optional_attendee_roles",
    "prep_checklist_items",
    "agenda_checklist_items",
    "closeout_checklist_items",
}


def _meeting_template_row(doc: dict[str, Any]) -> dict[str, Any]:
    row = dict(doc)
    for field_name in _MEETING_TEMPLATE_LIST_FIELDS:
        row[field_name] = _list_to_lines(row.get(field_name))
    return row


def _meeting_template_payload(form: dict[str, Any]) -> dict[str, Any]:
    name = str(form.get("name") or "").strip()
    slug = _slugify(form.get("slug") or name)
    return {
        "slug": slug,
        "name": name,
        "default_duration_minutes": int(form.get("default_duration_minutes") or 60),
        "agenda_sections": _lines_to_list(form.get("agenda_sections")),
        "required_attendee_roles": _lines_to_list(form.get("required_attendee_roles")),
        "optional_attendee_roles": _lines_to_list(form.get("optional_attendee_roles")),
        "prep_checklist_items": _lines_to_list(form.get("prep_checklist_items")),
        "agenda_checklist_items": _lines_to_list(form.get("agenda_checklist_items")),
        "closeout_checklist_items": _lines_to_list(form.get("closeout_checklist_items")),
        "appears_on_ics230_default": bool(form.get("appears_on_ics230_default")),
        "active": bool(form.get("active")),
    }


def _create_meeting_template(body: dict[str, Any]) -> dict[str, Any]:
    from sarapp_db.api.routers import meetings as meetings_router

    slug = _slugify(body.get("slug") or body.get("name"))
    return meetings_router.upsert_template(slug, body)


def _hazard_entries_to_lines(value: Any) -> str:
    lines: list[str] = []
    for entry in value or []:
        if not isinstance(entry, dict):
            continue
        hazard_type_id = entry.get("hazard_type_id")
        if hazard_type_id in (None, ""):
            continue
        sort_order = entry.get("sort_order", "")
        notes = str(entry.get("override_notes") or "").replace("\n", " ").strip()
        lines.append(f"{hazard_type_id} | {sort_order} | {notes}".rstrip(" |"))
    return "\n".join(lines)


def _hazard_entries_from_lines(value: Any) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for index, line in enumerate(str(value or "").splitlines(), start=1):
        parts = [part.strip() for part in line.split("|")]
        if not parts or not parts[0]:
            continue
        try:
            hazard_type_id = int(parts[0])
        except ValueError:
            continue
        try:
            sort_order = int(parts[1]) if len(parts) > 1 and parts[1] else index
        except ValueError:
            sort_order = index
        entries.append({
            "hazard_type_id": hazard_type_id,
            "sort_order": sort_order,
            "override_notes": parts[2] if len(parts) > 2 else "",
        })
    return entries


def _safety_template_row(doc: dict[str, Any]) -> dict[str, Any]:
    row = dict(doc)
    row["target_forms"] = _list_to_lines(row.get("target_forms"))
    row["hazard_entries"] = _hazard_entries_to_lines(row.get("hazard_entries"))
    return row


def _safety_template_payload(form: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(form.get("name") or "").strip(),
        "description": str(form.get("description") or ""),
        "scenario_type": str(form.get("scenario_type") or "General"),
        "target_forms": _lines_to_list(form.get("target_forms")),
        "hazard_entries": _hazard_entries_from_lines(form.get("hazard_entries")),
        "is_active": bool(form.get("is_active")),
        "notes": str(form.get("notes") or ""),
        "created_by": str(form.get("created_by") or ""),
        "updated_by": str(form.get("updated_by") or ""),
    }


def _gar_payload(gar_body_cls: type, form: dict[str, Any]) -> Any:
    name = str(form.get("name") or "").strip()
    groups: list[dict[str, Any]] = []
    group_count = int(form.get("gar_group_count") or 0)
    for group_index in range(group_count):
        group_name = str(form.get(f"gar_group_name_{group_index}") or "").strip()
        if not group_name:
            continue
        rows: list[dict[str, Any]] = []
        row_count = int(form.get(f"gar_row_count_{group_index}") or 0)
        for row_index in range(row_count):
            row_label = str(form.get(f"gar_row_label_{group_index}_{row_index}") or "").strip()
            if not row_label:
                continue
            options: list[dict[str, Any]] = []
            option_count = int(form.get(f"gar_option_count_{group_index}_{row_index}") or 0)
            for option_index in range(option_count):
                option_label = str(
                    form.get(f"gar_option_label_{group_index}_{row_index}_{option_index}") or ""
                ).strip()
                if not option_label:
                    continue
                points_raw = str(
                    form.get(f"gar_option_points_{group_index}_{row_index}_{option_index}") or "0"
                ).strip()
                options.append({
                    "id": f"o{len(options) + 1}",
                    "label": option_label,
                    "points": int(points_raw or 0),
                    "no_go": f"gar_option_no_go_{group_index}_{row_index}_{option_index}" in form,
                })
            if options:
                rows.append({"id": f"r{len(rows) + 1}", "label": row_label, "options": options})
        if rows:
            groups.append({"id": f"g{len(groups) + 1}", "name": group_name, "rows": rows})

    bands: list[dict[str, Any]] = []
    band_count = int(form.get("gar_band_count") or 0)
    for band_index in range(band_count):
        label = str(form.get(f"gar_band_label_{band_index}") or "").strip()
        if not label:
            continue
        floor_raw = str(form.get(f"gar_band_floor_{band_index}") or "0").strip()
        bands.append({
            "floor": int(floor_raw or 0),
            "label": label,
            "required_reviewer": str(form.get(f"gar_band_reviewer_{band_index}") or "").strip(),
        })

    return gar_body_cls(
        name=name,
        source=str(form.get("source") or ""),
        description=str(form.get("description") or ""),
        groups=groups,
        bands=bands,
        active=bool(form.get("active")),
        updated_by=str(form.get("updated_by") or ""),
    )


def _vehicle_create_payload(vehicle_body_cls: type, body: dict[str, Any]) -> Any:
    payload = {key: value for key, value in body.items() if value is not None}
    return vehicle_body_cls(**payload)


def _aircraft_create_payload(aircraft_body_cls: type, body: dict[str, Any]) -> Any:
    payload = {key: value for key, value in body.items() if value is not None}
    if not payload.get("aircraft_id") and payload.get("tail_number"):
        payload["aircraft_id"] = payload["tail_number"]
    return aircraft_body_cls(**payload)


def _certification_type_form_row(doc: dict[str, Any]) -> dict[str, Any]:
    row = dict(doc)
    row["tags"] = _list_to_csv(row.get("tags"))
    return row


def _certification_type_form_payload(form: dict[str, Any]) -> dict[str, Any]:
    parent_id = str(form.get("parent_id") or "").strip()
    return {
        "code": str(form.get("code") or "").strip(),
        "name": str(form.get("name") or "").strip(),
        "category": str(form.get("category") or "").strip(),
        "issuing_org": str(form.get("issuing_org") or "").strip(),
        "parent_id": int(parent_id) if parent_id.isdigit() else None,
        "tags": _csv_to_list(form.get("tags")),
        "is_active": bool(form.get("is_active", True)),
    }


def _qualification_type_form_row(doc: dict[str, Any]) -> dict[str, Any]:
    row = dict(doc)
    row["any_tags"] = _list_to_csv(row.get("any_tags"))
    row["all_tags"] = _list_to_csv(row.get("all_tags"))
    return row


def _qualification_type_form_payload(form: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": str(form.get("code") or "").strip(),
        "name": str(form.get("name") or "").strip(),
        "any_tags": _csv_to_list(form.get("any_tags")),
        "all_tags": _csv_to_list(form.get("all_tags")),
        "min_level": int(form.get("min_level") or 2),
        "is_active": bool(form.get("is_active", True)),
    }


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


def _org_short_name_by_name() -> dict[str, str]:
    from sarapp_db.api.routers import organizations as organizations_router

    return {
        str(o.get("name") or ""): str(o.get("short_name") or "")
        for o in organizations_router.list_organizations(search="")
    }


def _format_home_unit(name: Any, short_by_name: dict[str, str]) -> str:
    name = str(name or "")
    short = short_by_name.get(name, "")
    return f"{short} - {name}" if short and name else name


def _format_organization(name: Any, short_by_name: dict[str, str]) -> str:
    return _format_home_unit(name, short_by_name)


def _organization_list_cell(doc: dict[str, Any], field_name: str) -> Any:
    if field_name == "parent_organization_id":
        parent_name = doc.get("parent_organization_name")
        if parent_name:
            return _format_organization(parent_name, _org_short_name_by_name())
        return doc.get(field_name)
    if field_name == "organization_type_id":
        return doc.get("organization_type_name") or doc.get(field_name)
    if field_name == "default_rank_structure_id":
        return doc.get("default_rank_structure_name") or doc.get("effective_rank_structure_name") or doc.get(field_name)
    return doc.get(field_name)


def _rank_structure_list_cell(doc: dict[str, Any], field_name: str) -> Any:
    if field_name == "organization_type_id":
        return doc.get("organization_type_name") or doc.get(field_name)
    return doc.get(field_name)


def _rank_list_cell(doc: dict[str, Any], field_name: str) -> Any:
    if field_name == "rank_structure_id":
        return doc.get("rank_structure_name") or doc.get(field_name)
    return doc.get(field_name)


def _objective_template_title_by_id() -> dict[int, str]:
    from sarapp_db.api.routers import objective_templates as objective_templates_router

    result: dict[int, str] = {}
    for row in objective_templates_router.list_objective_templates(
        search="", include_archived=True, tag=""
    ):
        record_id = row.get("int_id_master") or row.get("int_id")
        if record_id is None:
            continue
        try:
            result[int(record_id)] = str(row.get("title") or row.get("code") or record_id)
        except (TypeError, ValueError):
            continue
    return result


def _strategy_template_list_cell(doc: dict[str, Any], field_name: str) -> Any:
    if field_name == "objective_template_id":
        objective_id = doc.get("objective_template_id")
        try:
            return _objective_template_title_by_id().get(int(objective_id), objective_id)
        except (TypeError, ValueError):
            return objective_id
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
        FieldSpec("organization_type_id", "Organization Type ID", input_type="select_fk", value_type="int"),
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
        FieldSpec("rank_structure_id", "Rank Structure ID", input_type="select_fk", value_type="int"),
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


def _organization_combo_options() -> list[tuple[str, str]]:
    return _personnel_org_rank_options()["organization_options"]


def _resource_type_combo_options() -> list[tuple[str, str]]:
    from sarapp_db.api.routers import resource_types as resource_types_router

    options: list[tuple[str, str]] = []
    for row in resource_types_router.list_resource_types(
        search_text="",
        category="All",
        source="All",
        active_filter="Active",
        include_inactive=False,
    ):
        resource_type_id = row.get("resource_type_id") or row.get("id")
        if resource_type_id is None:
            continue
        label = str(row.get("resource_name") or row.get("name") or resource_type_id)
        category = str(row.get("category") or "").strip()
        source = str(row.get("source") or "").strip()
        context = " - ".join(part for part in (category, source) if part)
        if context:
            label = f"{label} ({context})"
        options.append((str(resource_type_id), label))
    return sorted(options, key=lambda pair: pair[1].lower())


_AIRCRAFT_STATUS_OPTIONS = ["Available", "Assigned", "Out of Service", "Standby", "In Transit"]
_AIRCRAFT_TYPE_OPTIONS = ["Helicopter", "Fixed-Wing", "UAS", "Gyroplane", "Other"]
_AIRCRAFT_FUEL_OPTIONS = ["Jet A", "Avgas", "Electric", "Other"]
_AIRCRAFT_MED_CONFIG_OPTIONS = ["None", "Basic", "Advanced"]
_VEHICLE_STATUS_OPTIONS = ["Available", "In Service", "Out of Service", "Retired"]
_VEHICLE_TYPE_OPTIONS = ["Passenger Vehicle", "Utility", "Support", "Other"]
_BLOOD_TYPE_OPTIONS = ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
_STATE_CODES = [
    "", "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI",
    "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN",
    "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH",
    "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA",
    "WV", "WI", "WY",
]


def _build_collection_specs() -> dict[str, CollectionSpec]:
    # Imported lazily (not at module import time) so this module can be
    # imported without sarapp_db being on the path yet in contexts that
    # never actually serve the GUI.
    from sarapp_db.api.routers import personnel as personnel_router
    from sarapp_db.api.routers import equipment as equipment_router
    from sarapp_db.api.routers import organizations as organizations_router
    from sarapp_db.api.routers import vehicles as vehicles_router
    from sarapp_db.api.routers import aircraft as aircraft_router
    from sarapp_db.api.routers import resource_types as resource_types_router
    from sarapp_db.api.routers import hazard_types as hazard_types_router
    from sarapp_db.api.routers import hospitals as hospitals_router
    from sarapp_db.api.routers import objective_templates as objective_templates_router
    from sarapp_db.api.routers import strategy_templates as strategy_templates_router
    from sarapp_db.api.routers import communications as communications_router
    from sarapp_db.api.routers import canned_comm_entries as canned_comm_entries_router
    from sarapp_db.api.routers import meetings as meetings_router
    from sarapp_db.api.routers import safety_templates as safety_templates_router
    from sarapp_db.api.routers import gar_templates as gar_templates_router
    from sarapp_db.api.routers import certification_types as certification_types_router
    from sarapp_db.api.routers import qualification_types as qualification_types_router
    from modules.admin.resource_types.models.resource_type_models import RESOURCE_CATEGORIES, RESOURCE_SOURCES
    from modules.admin.hazard_types.models.hazard_type_models import HAZARD_CATEGORIES
    from modules.personnel.catalog_io import (
        PERSONNEL_FIELDS,
        PERSONNEL_FIELD_LABELS,
        build_personnel_import_payload,
        certification_catalogs,
        personnel_export_row,
    )
    from modules.logistics.equipment_catalog_io import FIELDS as EQUIPMENT_EXPORT_FIELDS

    equipment_export_field_keys = [f.key for f in EQUIPMENT_EXPORT_FIELDS]
    personnel_fields = [
        FieldSpec(
            f.key,
            f.label,
            input_type="select" if f.key in {
                "home_unit",
                "rank",
                "emergency_blood_type",
                "contact_state",
            } else "checkbox" if f.key == "is_medic" else "textarea" if f.key in {"notes", "contact_notes", "emergency_medical"} else "text",
        )
        for f in PERSONNEL_FIELDS
    ]
    equipment_fields = [
        FieldSpec(
            f.key,
            f.label,
            input_type="select" if f.key == "organization" else "textarea" if f.key == "notes" else "text",
        )
        for f in EQUIPMENT_EXPORT_FIELDS
    ]
    vehicle_fields = [
        FieldSpec("vehicle_id", "Vehicle ID"),
        FieldSpec("vin", "VIN"),
        FieldSpec("license_plate", "License Plate"),
        FieldSpec("year", "Year", input_type="number", value_type="int"),
        FieldSpec("make", "Make"),
        FieldSpec("model", "Model"),
        FieldSpec("capacity", "Capacity", input_type="number", value_type="int"),
        FieldSpec("type_id", "Type", input_type="select"),
        FieldSpec("status_id", "Status", input_type="select"),
        FieldSpec("organization", "Organization", input_type="select"),
        FieldSpec("resource_type_id", "Resource Type", input_type="select_fk", value_type="int"),
        FieldSpec("tags", "Tags", input_type="textarea"),
    ]
    aircraft_fields = [
        FieldSpec("aircraft_id", "Aircraft ID"),
        FieldSpec("callsign", "Callsign"),
        FieldSpec("type", "Type", input_type="select"),
        FieldSpec("make", "Make"),
        FieldSpec("model", "Model"),
        FieldSpec("base", "Base", input_type="combo"),
        FieldSpec("current_location", "Current Location"),
        FieldSpec("status", "Status", input_type="select"),
        FieldSpec("assigned_team_name", "Assigned Team"),
        FieldSpec("organization", "Organization", input_type="select"),
        FieldSpec("fuel_type", "Fuel Type", input_type="select"),
        FieldSpec("range_nm", "Range NM", input_type="number", value_type="int"),
        FieldSpec("endurance_hr", "Endurance Hours", input_type="number", value_type="float"),
        FieldSpec("cruise_kt", "Cruise KT", input_type="number", value_type="int"),
        FieldSpec("crew_min", "Minimum Crew", input_type="number", value_type="int"),
        FieldSpec("crew_max", "Maximum Crew", input_type="number", value_type="int"),
        FieldSpec("adsb_hex", "ADS-B Hex"),
        FieldSpec("radio_vhf_air", "VHF Air Radio", input_type="checkbox", value_type="bool"),
        FieldSpec("radio_vhf_sar", "VHF SAR Radio", input_type="checkbox", value_type="bool"),
        FieldSpec("radio_uhf", "UHF Radio", input_type="checkbox", value_type="bool"),
        FieldSpec("cap_hoist", "Hoist", input_type="checkbox", value_type="bool"),
        FieldSpec("cap_nvg", "Night Ops", input_type="checkbox", value_type="bool"),
        FieldSpec("cap_flir", "FLIR", input_type="checkbox", value_type="bool"),
        FieldSpec("cap_ifr", "IFR", input_type="checkbox", value_type="bool"),
        FieldSpec("payload_kg", "Payload / Winch KG", input_type="number", value_type="float"),
        FieldSpec("med_config", "Medical Config", input_type="select"),
        FieldSpec("serial_number", "Serial Number"),
        FieldSpec("year", "Year", input_type="number", value_type="int"),
        FieldSpec("owner_operator", "Owner / Operator"),
        FieldSpec("registration_exp", "Registration Expiration"),
        FieldSpec("inspection_due", "Inspection Due"),
        FieldSpec("last_100hr", "Last 100-Hour"),
        FieldSpec("next_100hr", "Next 100-Hour"),
        FieldSpec("notes", "Notes", input_type="textarea"),
    ]
    resource_type_fields = [
        FieldSpec("name", "Name"),
        FieldSpec("resource_name", "Display Name"),
        FieldSpec("category", "Category", input_type="select"),
        FieldSpec("source", "Source", input_type="select"),
        FieldSpec("owner_agency", "Owner Agency"),
        FieldSpec("description", "Description", input_type="textarea"),
        FieldSpec("default_unit", "Default Unit"),
        FieldSpec("typical_quantity", "Typical Quantity", input_type="number", value_type="float"),
        FieldSpec("typical_team_size", "Typical Team Size", input_type="number", value_type="int"),
        FieldSpec("is_kit_cache", "Kit / Cache", input_type="checkbox", value_type="bool"),
        FieldSpec("is_consumable", "Consumable", input_type="checkbox", value_type="bool"),
        FieldSpec("is_active", "Active", input_type="checkbox", value_type="bool"),
        FieldSpec("notes", "Notes", input_type="textarea"),
    ]
    resource_capability_fields = [
        FieldSpec("name", "Name"),
        FieldSpec("category", "Category"),
        FieldSpec("description", "Description", input_type="textarea"),
        FieldSpec("is_active", "Active", input_type="checkbox", value_type="bool"),
        FieldSpec("notes", "Notes", input_type="textarea"),
    ]
    hospital_fields = [
        FieldSpec("name", "Name"),
        FieldSpec("code", "Code"),
        FieldSpec("address", "Address"),
        FieldSpec("city", "City"),
        FieldSpec("state", "State", input_type="select"),
        FieldSpec("zip", "ZIP"),
        FieldSpec("phone", "Phone"),
        FieldSpec("contact_name", "Contact Name"),
        FieldSpec("latitude", "Latitude", value_type="float"),
        FieldSpec("longitude", "Longitude", value_type="float"),
        FieldSpec("notes", "Notes", input_type="textarea"),
    ]
    objective_template_fields = [
        FieldSpec("code", "Code"),
        FieldSpec("title", "Title"),
        FieldSpec("description", "Description", input_type="textarea"),
        FieldSpec("default_section", "Default Section", input_type="select"),
        FieldSpec("priority", "Priority", input_type="select"),
        FieldSpec("active", "Active", input_type="checkbox", value_type="bool"),
        FieldSpec("tags", "Tags"),
    ]
    strategy_template_fields = [
        FieldSpec("objective_template_id", "Objective Template", input_type="select_fk", value_type="int"),
        FieldSpec("title", "Title"),
        FieldSpec("description", "Description", input_type="textarea"),
        FieldSpec("assignment_kind", "Assignment Kind", input_type="select"),
        FieldSpec("branch", "Branch"),
        FieldSpec("division_group", "Division / Group"),
        FieldSpec("priority", "Priority", input_type="select"),
        FieldSpec("active", "Active", input_type="checkbox", value_type="bool"),
        FieldSpec("tags", "Tags"),
    ]
    meeting_template_fields = [
        FieldSpec("slug", "Slug"),
        FieldSpec("name", "Name"),
        FieldSpec("default_duration_minutes", "Default Duration Minutes", input_type="number", value_type="int"),
        FieldSpec("agenda_sections", "Agenda Sections", input_type="list"),
        FieldSpec("required_attendee_roles", "Required Attendee Roles", input_type="list"),
        FieldSpec("optional_attendee_roles", "Optional Attendee Roles", input_type="list"),
        FieldSpec("prep_checklist_items", "Prep Checklist Items", input_type="list"),
        FieldSpec("agenda_checklist_items", "Agenda Checklist Items", input_type="list"),
        FieldSpec("closeout_checklist_items", "Closeout Checklist Items", input_type="list"),
        FieldSpec("appears_on_ics230_default", "Appears On ICS-230 By Default", input_type="checkbox", value_type="bool"),
        FieldSpec("active", "Active", input_type="checkbox", value_type="bool"),
    ]
    safety_template_fields = [
        FieldSpec("name", "Name"),
        FieldSpec("description", "Description", input_type="textarea"),
        FieldSpec("scenario_type", "Scenario Type", input_type="select"),
        FieldSpec("target_forms", "Target Forms", input_type="list"),
        FieldSpec("hazard_entries", "Hazard Entries", input_type="list"),
        FieldSpec("is_active", "Active", input_type="checkbox", value_type="bool"),
        FieldSpec("notes", "Notes", input_type="textarea"),
        FieldSpec("created_by", "Created By"),
        FieldSpec("updated_by", "Updated By"),
    ]
    gar_template_fields = [
        FieldSpec("name", "Name"),
        FieldSpec("source", "Source"),
        FieldSpec("description", "Description", input_type="textarea"),
        FieldSpec("active", "Active", input_type="checkbox", value_type="bool"),
        FieldSpec("updated_by", "Updated By"),
    ]
    radio_channel_fields = [
        FieldSpec("name", "Name"),
        FieldSpec("function", "Function"),
        FieldSpec("rx_freq", "RX Frequency", input_type="number", value_type="float"),
        FieldSpec("tx_freq", "TX Frequency", input_type="number", value_type="float"),
        FieldSpec("rx_tone", "RX Tone"),
        FieldSpec("tx_tone", "TX Tone"),
        FieldSpec("system", "System"),
        FieldSpec("mode", "Mode", input_type="select"),
        FieldSpec("line_a", "ICS 205 Line A", input_type="checkbox", value_type="bool"),
        FieldSpec("line_c", "ICS 205 Line C", input_type="checkbox", value_type="bool"),
        FieldSpec("notes", "Notes", input_type="textarea"),
    ]
    canned_comm_fields = [
        FieldSpec("title", "Title"),
        FieldSpec("category", "Category"),
        FieldSpec("message", "Message", input_type="textarea"),
        FieldSpec("priority", "Priority", input_type="select"),
        FieldSpec("notification_level", "Notification Level", input_type="number", value_type="int"),
        FieldSpec("status_update", "Status Update"),
        FieldSpec("is_active", "Active", input_type="checkbox", value_type="bool"),
    ]
    hazard_type_fields = [
        FieldSpec("name", "Name"),
        FieldSpec("category", "Category", input_type="select"),
        FieldSpec("description", "Description", input_type="textarea"),
        FieldSpec("aliases", "Aliases"),
        FieldSpec("controls", "Controls"),
        FieldSpec("ppe", "PPE"),
        FieldSpec("standard_safety_language", "Standard Safety Language", input_type="textarea"),
        FieldSpec("default_spe_severity", "Default Severity", input_type="number", value_type="int"),
        FieldSpec("default_spe_probability", "Default Probability", input_type="number", value_type="int"),
        FieldSpec("default_spe_exposure", "Default Exposure", input_type="number", value_type="int"),
        FieldSpec("active", "Active", input_type="checkbox", value_type="bool"),
    ]

    specs = [
        CollectionSpec(
            key="personnel",
            title="Personnel",
            # The central catalog mints person_record_master, not
            # person_record — see data/db/sarapp_db/schemas/personnel_schema.py.
            record_field="person_record_master",
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
            # certification_catalogs() now reads a live Mongo-backed catalog
            # (see Design Documents/legacycode.md) rather than a hardcoded
            # Python list, so this is called fresh on each use instead of
            # once at router-build time — a cert type added/renamed while
            # the server is running must be visible immediately, not only
            # after a restart.
            export_row_fn=lambda doc: personnel_export_row(doc, certification_catalogs()[1]),
            import_payload_fn=lambda row: build_personnel_import_payload(row, certification_catalogs()[0]),
            form_row_fn=lambda doc: personnel_export_row(doc, certification_catalogs()[1]),
            form_payload_fn=lambda row: build_personnel_import_payload(row, certification_catalogs()[0]),
            list_fields=["person_id", "first_name", "last_name", "callsign", "rank", "home_unit", "phone", "is_medic"],
            inline_edit_fields=["person_id", "first_name", "last_name", "callsign", "rank", "home_unit", "phone", "is_medic"],
        ),
        CollectionSpec(
            key="equipment",
            title="Equipment",
            record_field="equipment_record_master",
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
            list_fields=["name", "type", "id_number", "serial_number", "organization", "condition"],
            inline_edit_fields=["organization"],
        ),
        CollectionSpec(
            key="vehicles",
            title="Vehicles",
            record_field="vehicle_record_master",
            fields=vehicle_fields,
            list_fn=lambda: vehicles_router.list_vehicles(search="", status_filter="", type_filter=""),
            get_fn=vehicles_router.get_vehicle,
            create_fn=lambda body: vehicles_router.create_vehicle(
                _vehicle_create_payload(vehicles_router.VehicleBody, body)
            ),
            update_fn=vehicles_router.update_vehicle,
            delete_fn=vehicles_router.delete_vehicle,
            list_fields=["vehicle_id", "license_plate", "type_id", "status_id", "organization"],
            inline_edit_fields=["type_id", "status_id", "organization"],
        ),
        CollectionSpec(
            key="aircraft",
            title="Aircraft",
            record_field="aircraft_record_master",
            fields=aircraft_fields,
            list_fn=lambda: aircraft_router.list_aircraft(search="", status="", type_filter=""),
            get_fn=aircraft_router.get_aircraft,
            create_fn=lambda body: aircraft_router.create_aircraft(
                _aircraft_create_payload(aircraft_router.AircraftBody, body)
            ),
            update_fn=aircraft_router.update_aircraft,
            delete_fn=aircraft_router.delete_aircraft,
            list_fields=["aircraft_id", "callsign", "type", "status", "organization", "base"],
            inline_edit_fields=["organization"],
        ),
        CollectionSpec(
            key="hospitals",
            title="Hospitals",
            record_field="id_master",
            fields=hospital_fields,
            list_fn=lambda: hospitals_router.list_hospitals(search=""),
            get_fn=hospitals_router.get_hospital,
            create_fn=hospitals_router.create_hospital,
            update_fn=hospitals_router.update_hospital,
            delete_fn=hospitals_router.delete_hospital,
            list_fields=["name", "code", "city", "state", "phone", "contact_name"],
        ),
        CollectionSpec(
            key="hazard-types",
            title="Hazard Types",
            record_field="id_master",
            fields=hazard_type_fields,
            list_fn=lambda: hazard_types_router.list_hazard_types(
                search_text="", category="All", active_filter="", include_inactive=True
            ),
            get_fn=hazard_types_router.get_hazard_type,
            create_fn=hazard_types_router.create_hazard_type,
            update_fn=hazard_types_router.save_hazard_type,
            delete_fn=None,
            form_row_fn=_hazard_form_row,
            export_row_fn=_hazard_form_row,
            import_payload_fn=lambda row: _hazard_form_payload(
                hazard_types_router.SaveHazardTypeRequest,
                hazard_types_router.DefaultSpeInput,
                row,
            ),
            form_payload_fn=lambda row: _hazard_form_payload(
                hazard_types_router.SaveHazardTypeRequest,
                hazard_types_router.DefaultSpeInput,
                row,
            ),
            list_fields=["name", "category", "description", "active"],
        ),
        CollectionSpec(
            key="objective-templates",
            title="Objective Templates",
            record_field="int_id_master",
            fields=objective_template_fields,
            list_fn=lambda: objective_templates_router.list_objective_templates(
                search="", include_archived=True, tag=""
            ),
            get_fn=objective_templates_router.get_objective_template,
            create_fn=objective_templates_router.create_objective_template,
            update_fn=objective_templates_router.update_objective_template,
            delete_fn=objective_templates_router.delete_objective_template,
            form_row_fn=_template_form_row,
            form_payload_fn=_objective_template_payload,
            export_row_fn=_template_form_row,
            import_payload_fn=_objective_template_payload,
            list_fields=["code", "title", "default_section", "priority", "active"],
        ),
        CollectionSpec(
            key="strategy-templates",
            title="Strategy Templates",
            record_field="int_id_master",
            fields=strategy_template_fields,
            list_fn=lambda: strategy_templates_router.list_strategy_templates(
                search="", include_archived=True, objective_template_id=None, tag=""
            ),
            get_fn=strategy_templates_router.get_strategy_template,
            create_fn=strategy_templates_router.create_strategy_template,
            update_fn=strategy_templates_router.update_strategy_template,
            delete_fn=strategy_templates_router.delete_strategy_template,
            form_row_fn=_template_form_row,
            form_payload_fn=_strategy_template_payload,
            export_row_fn=_template_form_row,
            import_payload_fn=_strategy_template_payload,
            list_cell_fn=_strategy_template_list_cell,
            list_fields=["title", "objective_template_id", "assignment_kind", "priority", "active"],
        ),
        CollectionSpec(
            key="meeting-templates",
            title="Meeting Templates",
            record_field="slug",
            fields=meeting_template_fields,
            list_fn=lambda: meetings_router.list_templates(active_only=False),
            get_fn=meetings_router.get_template,
            create_fn=_create_meeting_template,
            update_fn=meetings_router.upsert_template,
            delete_fn=None,
            record_id_type="str",
            form_row_fn=_meeting_template_row,
            form_payload_fn=_meeting_template_payload,
            export_row_fn=_meeting_template_row,
            import_payload_fn=_meeting_template_payload,
            list_fields=["name", "slug", "default_duration_minutes", "appears_on_ics230_default", "active"],
        ),
        CollectionSpec(
            key="safety-analysis-templates",
            title="Safety Analysis Templates",
            record_field="template_id_master",
            fields=safety_template_fields,
            list_fn=lambda: safety_templates_router.list_templates(
                search_text=None, scenario_type=None, include_inactive=True
            ),
            get_fn=safety_templates_router.get_template,
            create_fn=safety_templates_router.create_template,
            update_fn=safety_templates_router.update_template,
            delete_fn=safety_templates_router.delete_template,
            form_row_fn=_safety_template_row,
            form_payload_fn=_safety_template_payload,
            export_row_fn=_safety_template_row,
            import_payload_fn=_safety_template_payload,
            list_fields=["name", "scenario_type", "target_forms", "is_active"],
        ),
        CollectionSpec(
            key="gar-templates",
            title="GAR Templates",
            record_field="id_master",
            fields=gar_template_fields,
            list_fn=lambda: gar_templates_router.list_gar_templates(include_inactive=True),
            get_fn=gar_templates_router.get_gar_template,
            create_fn=lambda body: gar_templates_router.create_gar_template(
                _gar_payload(gar_templates_router.SaveGarTemplateRequest, body)
            ),
            update_fn=lambda record_id, body: gar_templates_router.save_gar_template(
                record_id,
                _gar_payload(gar_templates_router.SaveGarTemplateRequest, body),
            ),
            delete_fn=None,
            form_payload_fn=lambda row: row,
            list_fields=["name", "source", "description", "active"],
        ),
        CollectionSpec(
            key="radio-channels",
            title="Radio Channels",
            record_field="id",
            fields=radio_channel_fields,
            list_fn=lambda: communications_router.list_master_channels(search=None, band=None, mode=None),
            get_fn=communications_router.get_master_channel,
            create_fn=communications_router.create_master_channel,
            update_fn=communications_router.update_master_channel,
            delete_fn=communications_router.delete_master_channel,
            list_fields=["name", "function", "rx_freq", "tx_freq", "mode", "line_a", "line_c"],
        ),
        CollectionSpec(
            key="canned-comm-entries",
            title="Canned Comm Entries",
            record_field="id_master",
            fields=canned_comm_fields,
            list_fn=lambda: canned_comm_entries_router.list_entries(search="", active_only=False),
            get_fn=canned_comm_entries_router.get_entry,
            create_fn=canned_comm_entries_router.create_entry,
            update_fn=canned_comm_entries_router.update_entry,
            delete_fn=canned_comm_entries_router.delete_entry,
            list_fields=["title", "category", "priority", "notification_level", "is_active"],
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
            list_cell_fn=_rank_list_cell,
        ),
        CollectionSpec(
            key="resource-types",
            title="Resource Types",
            record_field="id",
            fields=resource_type_fields,
            list_fn=lambda: resource_types_router.list_resource_types(
                search_text="", category="All", source="All", active_filter="All", include_inactive=True
            ),
            get_fn=lambda record_id: resource_types_router.get_resource_type(str(record_id)),
            create_fn=lambda body: resource_types_router.create_resource_type(
                _resource_type_create_payload(resource_types_router.SaveResourceTypeRequest, body)
            ),
            update_fn=lambda record_id, body: resource_types_router.save_resource_type(
                str(record_id),
                _resource_type_update_payload(resource_types_router.SaveResourceTypeRequest, body),
            ),
            delete_fn=None,
            list_fields=["name", "resource_name", "category", "source", "is_kit_cache", "is_active"],
        ),
        CollectionSpec(
            key="resource-capabilities",
            title="Resource Capabilities",
            record_field="id",
            fields=resource_capability_fields,
            list_fn=lambda: resource_types_router.list_capabilities(include_inactive=True, category="All"),
            get_fn=_get_resource_capability,
            create_fn=_create_resource_capability,
            update_fn=_update_resource_capability,
            delete_fn=None,
            list_fields=["name", "category", "description", "is_active"],
        ),
        CollectionSpec(
            key="certification-types",
            title="Certification Types",
            record_field="id",
            fields=[
                FieldSpec("code", "Code"),
                FieldSpec("name", "Name"),
                FieldSpec("category", "Category"),
                FieldSpec("issuing_org", "Issuing Org"),
                FieldSpec("parent_id", "Parent ID", value_type="int"),
                FieldSpec("tags", "Qualification Tags"),
                FieldSpec("is_active", "Active", input_type="checkbox"),
            ],
            list_fn=lambda: certification_types_router.list_certification_types(search="", category="", include_inactive=True),
            get_fn=certification_types_router.get_certification_type,
            create_fn=certification_types_router.create_certification_type,
            update_fn=certification_types_router.update_certification_type,
            delete_fn=None,
            form_row_fn=_certification_type_form_row,
            form_payload_fn=_certification_type_form_payload,
            list_fields=["code", "name", "category", "issuing_org", "is_active"],
        ),
        CollectionSpec(
            key="qualification-types",
            title="Qualification Types",
            record_field="id",
            fields=[
                FieldSpec("code", "Code"),
                FieldSpec("name", "Name"),
                FieldSpec("any_tags", "Any Of These Tags (comma-separated)"),
                FieldSpec("all_tags", "All Of These Tags (comma-separated)"),
                FieldSpec("min_level", "Minimum Level", input_type="number", value_type="int"),
                FieldSpec("is_active", "Active", input_type="checkbox"),
            ],
            list_fn=lambda: qualification_types_router.list_qualification_types(search="", include_inactive=True),
            get_fn=qualification_types_router.get_qualification_type,
            create_fn=qualification_types_router.create_qualification_type,
            update_fn=qualification_types_router.update_qualification_type,
            delete_fn=None,
            form_row_fn=_qualification_type_form_row,
            form_payload_fn=_qualification_type_form_payload,
            list_fields=["code", "name", "min_level", "is_active"],
        ),
        CollectionSpec(
            key="console-users",
            title="Console Users",
            record_field="int_id",
            fields=[
                FieldSpec("username", "Username"),
                FieldSpec("password", "Password", input_type="password"),
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
    td[data-inline-td] {{ cursor:text; }}
    .inline-cell {{ display:block; }}
    .inline-cell.saving {{ opacity:.5; }}
    .inline-edit-input {{ width:100%; padding:4px 6px; font:inherit; border-radius:4px; border:1px solid var(--accent); background:var(--field); color:var(--text); }}
    .inline-edit-input[type="checkbox"] {{ width:auto; }}
    .inline-edit-wrap {{ position:relative; min-width:180px; }}
    .inline-edit-wrap.selecting .inline-edit-input {{ padding-right:24px; }}
    .inline-edit-wrap.selecting::after {{ content:"v"; position:absolute; right:8px; top:50%; transform:translateY(-50%); color:var(--muted); pointer-events:none; font-size:.78rem; }}
    .inline-edit-list {{ position:fixed; z-index:50; max-height:240px; overflow:auto; background:var(--panel-2); border:1px solid var(--line); border-radius:6px; box-shadow:0 8px 24px rgba(0,0,0,.35); }}
    .inline-edit-option {{ padding:8px 10px; cursor:pointer; font-size:.92rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
    .inline-edit-option:hover {{ background:rgba(103,183,255,.12); }}
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
    .gar-editor {{ display:flex; flex-direction:column; gap:14px; margin-top:16px; }}
    .gar-group, .gar-row, .gar-option, .gar-band {{ border:1px solid var(--line); border-radius:6px; padding:10px; background:rgba(255,255,255,.02); }}
    .gar-group, .gar-row {{ display:flex; flex-direction:column; gap:10px; }}
    .gar-row {{ margin-left:18px; }}
    .gar-option, .gar-band {{ display:grid; grid-template-columns:minmax(180px, 1fr) 90px 140px auto; gap:10px; align-items:end; }}
    .gar-band {{ grid-template-columns:90px minmax(180px, 1fr) minmax(160px, 1fr) auto; }}
    .gar-subhead {{ display:flex; gap:10px; align-items:end; justify-content:space-between; flex-wrap:wrap; }}
    .gar-subhead label {{ flex:1; min-width:220px; }}
    .gar-actions {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; }}
    .cert-field {{ grid-column:1 / -1; }}
    .cert-editor {{ display:flex; flex-direction:column; gap:10px; }}
    .cert-row {{ display:flex; gap:10px; align-items:center; }}
    .cert-row select {{ flex:1; }}
    .cert-row select[data-cert-level] {{ flex:0 0 140px; }}
    .tag-picker-options {{ display:flex; flex-wrap:wrap; gap:6px 16px; }}
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

  // Inline cell editing — double-clicking a cell in a table whose <table>
  // carries data-inline-collection (currently just Personnel) edits that
  // one field in place via a small fetch to /inline/<field>, instead of
  // navigating to the record's full edit page.
  document.querySelectorAll("table[data-inline-collection]").forEach((table) => {{
    const collectionKey = table.dataset.inlineCollection;
    table.querySelectorAll(".inline-cell").forEach((span) => {{
      span.addEventListener("dblclick", (event) => {{
        event.stopPropagation();
        if (span.querySelector("input")) return;
        const field = span.dataset.field;
        const record = span.dataset.record;
        const editorType = span.dataset.editor || "text";
        const rawValue = span.dataset.rawValue || "";
        const originalHtml = span.innerHTML;
        let options = [];
        try {{
          options = JSON.parse(span.dataset.options || "[]");
        }} catch (err) {{
          options = [];
        }}
        if (collectionKey === "personnel" && field === "rank") {{
          let rankByOrg = {{}};
          try {{
            rankByOrg = JSON.parse(table.dataset.rankByOrg || "{{}}");
          }} catch (err) {{
            rankByOrg = {{}};
          }}
          const row = span.closest("tr");
          const homeUnitCell = row ? row.querySelector('.inline-cell[data-field="home_unit"]') : null;
          const homeUnit = homeUnitCell ? (homeUnitCell.dataset.rawValue || "") : "";
          const rankValues = rankByOrg[homeUnit] || [];
          if (rankValues.length) {{
            options = rankValues.map((value) => ({{ id: value, label: value }}));
            if (rawValue && !rankValues.includes(rawValue)) {{
              options.unshift({{ id: rawValue, label: rawValue }});
            }}
          }}
        }}

        const input = document.createElement("input");
        input.className = "inline-edit-input";
        let wrapper = null;
        let optionList = null;
        let selectedValue = rawValue;

        function renderOptions(filterText) {{
          if (!optionList) return;
          const needle = filterText.trim().toLowerCase();
          const matches = (needle
            ? options.filter((opt) => opt.label.toLowerCase().includes(needle))
            : options).slice(0, 50);
          const rect = input.getBoundingClientRect();
          optionList.style.left = `${{rect.left}}px`;
          optionList.style.top = `${{rect.bottom + 2}}px`;
          optionList.style.width = `${{rect.width}}px`;
          optionList.innerHTML = "";
          matches.forEach((opt) => {{
            const row = document.createElement("div");
            row.className = "inline-edit-option";
            row.textContent = opt.label;
            row.addEventListener("mousedown", (mouseEvent) => {{
              mouseEvent.preventDefault();
              selectedValue = opt.id;
              input.value = opt.label;
              optionList.hidden = true;
              save();
            }});
            optionList.appendChild(row);
          }});
          optionList.hidden = matches.length === 0;
        }}

        if (editorType === "checkbox") {{
          input.type = "checkbox";
          input.checked = ["1", "true", "yes", "y", "on"].includes(rawValue.toLowerCase());
        }} else if (editorType === "select") {{
          wrapper = document.createElement("div");
          wrapper.className = "inline-edit-wrap selecting";
          input.type = "text";
          input.value = (options.find((opt) => opt.id === rawValue) || {{ label: rawValue }}).label;
          input.setAttribute("autocomplete", "off");
          optionList = document.createElement("div");
          optionList.className = "inline-edit-list";
          optionList.hidden = true;
        }} else {{
          input.type = "text";
          input.value = rawValue;
        }}
        span.innerHTML = "";
        if (wrapper) {{
          wrapper.appendChild(input);
          wrapper.appendChild(optionList);
          span.appendChild(wrapper);
        }} else {{
          span.appendChild(input);
        }}
        input.focus();
        if (editorType !== "checkbox") input.select();
        if (editorType === "select") renderOptions("");

        let settled = false;
        function cancel() {{
          if (settled) return;
          settled = true;
          span.innerHTML = originalHtml;
        }}
        function save() {{
          if (settled) return;
          settled = true;
          const value = editorType === "checkbox" ? (input.checked ? "1" : "") : editorType === "select" ? selectedValue : input.value;
          span.classList.add("saving");
          const body = new URLSearchParams({{ value: value }});
          fetch(`${{window.location.pathname.split("/gui/")[0]}}/gui/${{collectionKey}}/${{record}}/inline/${{field}}`, {{
            method: "POST",
            headers: {{ "Content-Type": "application/x-www-form-urlencoded" }},
            body: body.toString(),
          }})
            .then((response) => {{
              if (!response.ok) throw new Error("save failed");
              return response.json();
            }})
            .then((data) => {{
              span.dataset.rawValue = data.raw || "";
              span.textContent = data.display || "";
              span.classList.remove("saving");
            }})
            .catch(() => {{
              span.classList.remove("saving");
              span.innerHTML = originalHtml;
              window.alert("Could not save that change.");
            }});
        }}

        if (editorType === "checkbox") {{
          input.addEventListener("change", save);
          input.addEventListener("blur", () => window.setTimeout(() => {{ if (!settled) save(); }}, 0));
        }} else if (editorType === "select") {{
          input.addEventListener("focus", () => renderOptions(input.value));
          input.addEventListener("click", () => renderOptions(input.value));
          input.addEventListener("input", () => {{
            selectedValue = "";
            renderOptions(input.value);
          }});
          input.addEventListener("blur", () => window.setTimeout(() => {{
            if (optionList) optionList.hidden = true;
            if (!settled) save();
          }}, 150));
        }} else {{
          input.addEventListener("blur", save);
        }}
        input.addEventListener("keydown", (keyEvent) => {{
          if (keyEvent.key === "Enter") {{
            keyEvent.preventDefault();
            save();
          }} else if (keyEvent.key === "Escape") {{
            keyEvent.preventDefault();
            cancel();
          }}
        }});
      }});
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
        is_checked = (
            field.name in {"is_active", "active", "appears_on_ics230_default"} and value is None
        ) or str(value).strip().lower() in {"1", "true", "yes", "y", "on"}
        checked = "checked" if is_checked else ""
        return f'<input type="checkbox" name="{escape(field.name)}" {checked}>'
    if field.input_type == "password":
        return f'<input type="password" name="{escape(field.name)}" value="{safe_value}" autocomplete="new-password">'
    if field.input_type == "number" or (field.input_type == "text" and field.value_type in {"int", "float"}):
        step = "1" if field.value_type == "int" else "0.1"
        return f'<input type="number" step="{step}" name="{escape(field.name)}" value="{safe_value}">'
    if field.input_type == "combo":
        options = list((combo_options or {}).get(field.name, []))
        list_id = f"list-{field.name}"
        options_html = "".join(f'<option value="{escape(str(opt_id))}">{escape(str(label))}</option>' for opt_id, label in options)
        return (
            f'<input type="text" name="{escape(field.name)}" value="{safe_value}" '
            f'list="{escape(list_id)}" autocomplete="off">'
            f'<datalist id="{escape(list_id)}">{options_html}</datalist>'
        )
    if field.input_type in ("select_fk", "select"):
        options = list((combo_options or {}).get(field.name, []))
        current = str(value) if value not in (None, "") else ""
        if field.input_type == "select" and current and current not in {opt_id for opt_id, _ in options}:
            options = [(current, current)] + options
        disabled = field.input_type == "select" and field.name == "rank" and not options and not current
        return _combo_html(
            field.name, value, options, disabled=disabled, depends_on=(combo_depends or {}).get(field.name)
        )
    if field.input_type in {"textarea", "list"}:
        return f'<textarea name="{escape(field.name)}" rows="3">{safe_value}</textarea>'
    return f'<input type="text" name="{escape(field.name)}" value="{safe_value}">'


_CERT_LEVEL_OPTIONS = [(1, "Trainee"), (2, "Qualified"), (3, "Evaluator")]


def _personnel_certification_rows(value: Any) -> list[dict[str, Any]]:
    """Parse a personnel record's `certifications` field (the "CODE:level;
    CODE:level" string format — see modules/personnel/catalog_io.py's
    format_certifications/parse_certifications) into rows with catalog
    display data, for pre-populating the certifications picker below."""
    from modules.personnel.catalog_io import certification_catalogs, parse_certifications

    catalog_by_code, catalog_by_id = certification_catalogs()
    rows: list[dict[str, Any]] = []
    for cert in parse_certifications(value, catalog_by_code):
        catalog_row = catalog_by_id.get(cert["cert_type_id"]) or {}
        code = catalog_row.get("code") or str(cert["cert_type_id"])
        rows.append({"code": code, "name": catalog_row.get("name", ""), "level": cert["level"]})
    return rows


def _personnel_certifications_picker_html(value: Any) -> str:
    """Render the personnel edit form's certifications field as an
    add/remove picker (one row per cert: a certification dropdown + a
    level dropdown), matching the desktop client's Certifications tab
    (ui/personnel/ui_personnel.py) instead of the old plain comma-string
    text box. The picker still submits a single hidden `certifications`
    field in the same "CODE:level; CODE:level" string `parse_certifications`
    already understands — serialized by JS on submit — so no backend
    parsing changes are needed."""
    from modules.personnel.catalog_io import certification_catalogs

    _, catalog_by_id = certification_catalogs()
    catalog_options = sorted(
        {(row.get("code") or str(cert_id), row.get("name") or "") for cert_id, row in catalog_by_id.items()},
        key=lambda pair: pair[0],
    )
    rows = _personnel_certification_rows(value)

    def code_options_html(selected: str) -> str:
        blank = '<option value="">Select certification...</option>' if not selected else ""
        options = "".join(
            f'<option value="{escape(code)}"{" selected" if code == selected else ""}>{escape(code)} - {escape(name)}</option>'
            for code, name in catalog_options
        )
        return blank + options

    def level_options_html(selected: int) -> str:
        return "".join(
            f'<option value="{level}"{" selected" if level == selected else ""}>{escape(label)}</option>'
            for level, label in _CERT_LEVEL_OPTIONS
        )

    def row_html(code: str = "", name: str = "", level: int = 1) -> str:
        return (
            '<div class="cert-row" data-cert-row>'
            f'<select data-cert-code>{code_options_html(code)}</select>'
            f'<select data-cert-level>{level_options_html(level)}</select>'
            '<button type="button" class="danger" data-remove-cert-row>Remove</button>'
            "</div>"
        )

    row_blocks = "".join(row_html(r["code"], r["name"], r["level"]) for r in rows)
    catalog_json = json.dumps(
        [{"code": code, "name": name} for code, name in catalog_options], separators=(",", ":")
    ).replace("</", "<\\/")
    safe_value = escape(str(value)) if value is not None else ""
    script = """<script>
(() => {
  const wrap = document.currentScript.closest("[data-cert-editor]");
  const form = wrap.closest("form");
  const rowsEl = wrap.querySelector("[data-cert-rows]");
  const hidden = wrap.querySelector("[data-cert-value]");
  const catalog = JSON.parse(wrap.querySelector("[data-cert-catalog]").textContent);
  const levels = [[1, "Trainee"], [2, "Qualified"], [3, "Evaluator"]];
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const codeOptions = (selected) => `<option value="">Select certification...</option>` +
    catalog.map((c) => `<option value="${esc(c.code)}"${c.code === selected ? " selected" : ""}>${esc(c.code)} - ${esc(c.name)}</option>`).join("");
  const levelOptions = (selected) => levels.map(([v, l]) => `<option value="${v}"${v === selected ? " selected" : ""}>${l}</option>`).join("");
  const newRow = () => `<div class="cert-row" data-cert-row><select data-cert-code>${codeOptions("")}</select><select data-cert-level>${levelOptions(1)}</select><button type="button" class="danger" data-remove-cert-row>Remove</button></div>`;
  wrap.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    if (button.matches("[data-add-cert-row]")) rowsEl.insertAdjacentHTML("beforeend", newRow());
    if (button.matches("[data-remove-cert-row]")) button.closest("[data-cert-row]").remove();
  });
  form.addEventListener("submit", () => {
    const parts = [...rowsEl.querySelectorAll("[data-cert-row]")].map((row) => {
      const code = row.querySelector("[data-cert-code]").value;
      const level = row.querySelector("[data-cert-level]").value;
      return code ? `${code}:${level}` : null;
    }).filter(Boolean);
    hidden.value = parts.join("; ");
  });
})();
</script>"""
    return f"""<div class="cert-editor" data-cert-editor>
  <input type="hidden" name="certifications" data-cert-value value="{safe_value}">
  <script type="application/json" data-cert-catalog>{catalog_json}</script>
  <div data-cert-rows>{row_blocks}</div>
  <button type="button" data-add-cert-row>Add Certification</button>
  {script}
</div>"""


def _qualification_tag_vocabulary() -> list[str]:
    """Distinct tags referenced by any qualification type's `any_tags`/
    `all_tags` — the controlled vocabulary a certification type's own tags
    are picked from (see `_certification_tags_picker_html` below and
    Design Documents/Instructions/mongodb_schema_decisions.md). A cert's
    tags only mean anything insofar as some qualification's any_tags/
    all_tags references them, so the qualification catalog is the source
    of truth for which tags exist, not free text typed on the cert."""
    from sarapp_db.api.routers.qualification_types import list_qualification_types

    tags: set[str] = set()
    for qualification in list_qualification_types(search="", include_inactive=True):
        tags.update(qualification.get("any_tags") or [])
        tags.update(qualification.get("all_tags") or [])
    return sorted(tags)


def _certification_tags_picker_html(value: Any) -> str:
    """Render a certification type's `tags` field as a checklist of the
    qualification tag vocabulary instead of a free-text box, so a cert can
    only be tagged with something a qualification type actually looks for
    — no typos, no tags that silently match nothing."""
    current = {tag.strip().upper() for tag in _csv_to_list(value)}
    vocabulary = _qualification_tag_vocabulary()
    safe_value = escape(str(value)) if value is not None else ""
    if not vocabulary:
        return (
            f'<input type="hidden" name="tags" value="{safe_value}">'
            '<p class="muted">No qualification tags exist yet — add a Qualification Type with Any/All tags first, then they\'ll be pickable here.</p>'
        )
    checkboxes = "".join(
        f'<label class="compact-check"><input type="checkbox" value="{escape(tag)}" data-cert-tag-checkbox'
        f'{" checked" if tag in current else ""}> {escape(tag)}</label>'
        for tag in vocabulary
    )
    script = """<script>
(() => {
  const wrap = document.currentScript.closest("[data-cert-tags-editor]");
  const form = wrap.closest("form");
  const hidden = wrap.querySelector("[data-cert-tags-value]");
  form.addEventListener("submit", () => {
    const checked = [...wrap.querySelectorAll("[data-cert-tag-checkbox]:checked")].map((cb) => cb.value);
    hidden.value = checked.join(", ");
  });
})();
</script>"""
    return f"""<div class="tag-picker" data-cert-tags-editor>
  <input type="hidden" name="tags" data-cert-tags-value value="{safe_value}">
  <div class="tag-picker-options">{checkboxes}</div>
  {script}
</div>"""


def _cell_html(value: Any) -> str:
    text = _stringify(value)
    if len(text) > 180:
        text = f"{text[:177]}..."
    return escape(text)


def _json_attr(value: Any) -> str:
    return escape(json.dumps(value, separators=(",", ":")).replace("</", "<\\/"), quote=True)


def _gar_template_form_html(doc: dict[str, Any], *, action: str, submit_label: str) -> str:
    groups = list(doc.get("groups") or [{
        "name": "New Group",
        "rows": [{"label": "New Row", "options": [{"label": "New Option", "points": 0, "no_go": False}]}],
    }])
    bands = list(doc.get("bands") or [{"floor": 0, "label": "New Band", "required_reviewer": ""}])

    group_blocks: list[str] = []
    for gi, group in enumerate(groups):
        row_blocks: list[str] = []
        rows = list(group.get("rows") or [])
        for ri, row in enumerate(rows):
            option_blocks: list[str] = []
            options = list(row.get("options") or [])
            for oi, option in enumerate(options):
                checked = "checked" if option.get("no_go") else ""
                option_blocks.append(
                    f'<div class="gar-option" data-gar-option>'
                    f'<label>Option<input type="text" name="gar_option_label_{gi}_{ri}_{oi}" value="{escape(str(option.get("label") or ""))}"></label>'
                    f'<label>Points<input type="number" step="1" name="gar_option_points_{gi}_{ri}_{oi}" value="{escape(str(option.get("points") or 0))}"></label>'
                    f'<label class="compact-check"><input type="checkbox" name="gar_option_no_go_{gi}_{ri}_{oi}" {checked}> No-Go</label>'
                    f'<button type="button" class="danger" data-remove-block>Remove</button>'
                    f'</div>'
                )
            row_blocks.append(
                f'<div class="gar-row" data-gar-row>'
                f'<div class="gar-subhead"><label>Row Label<input type="text" name="gar_row_label_{gi}_{ri}" value="{escape(str(row.get("label") or ""))}"></label>'
                f'<div class="gar-actions"><button type="button" data-add-option>Add Option</button><button type="button" class="danger" data-remove-block>Remove Row</button></div></div>'
                f'<input type="hidden" name="gar_option_count_{gi}_{ri}" value="{len(options)}" data-option-count>'
                f'<div data-gar-options>{"".join(option_blocks)}</div></div>'
            )
        group_blocks.append(
            f'<div class="gar-group" data-gar-group>'
            f'<div class="gar-subhead"><label>Group Name<input type="text" name="gar_group_name_{gi}" value="{escape(str(group.get("name") or ""))}"></label>'
            f'<div class="gar-actions"><button type="button" data-add-row>Add Row</button><button type="button" class="danger" data-remove-block>Remove Group</button></div></div>'
            f'<input type="hidden" name="gar_row_count_{gi}" value="{len(rows)}" data-row-count>'
            f'<div data-gar-rows>{"".join(row_blocks)}</div></div>'
        )

    band_blocks = [
        f'<div class="gar-band" data-gar-band>'
        f'<label>Floor<input type="number" step="1" name="gar_band_floor_{bi}" value="{escape(str(band.get("floor") or 0))}"></label>'
        f'<label>Label<input type="text" name="gar_band_label_{bi}" value="{escape(str(band.get("label") or ""))}"></label>'
        f'<label>Required Reviewer<input type="text" name="gar_band_reviewer_{bi}" value="{escape(str(band.get("required_reviewer") or ""))}"></label>'
        f'<button type="button" class="danger" data-remove-block>Remove</button></div>'
        for bi, band in enumerate(bands)
    ]
    active_checked = "checked" if doc.get("active", True) else ""
    script = """<script>
(() => {
  const form = document.currentScript.closest("form");
  const groups = form.querySelector("[data-gar-groups]");
  const bands = form.querySelector("[data-gar-bands]");
  const groupCount = form.querySelector("[data-group-count]");
  const bandCount = form.querySelector("[data-band-count]");
  const option = () => `<div class="gar-option" data-gar-option><label>Option<input type="text" name="gar_option_label_0_0_0" value="New Option"></label><label>Points<input type="number" step="1" name="gar_option_points_0_0_0" value="0"></label><label class="compact-check"><input type="checkbox" name="gar_option_no_go_0_0_0"> No-Go</label><button type="button" class="danger" data-remove-block>Remove</button></div>`;
  const row = () => `<div class="gar-row" data-gar-row><div class="gar-subhead"><label>Row Label<input type="text" name="gar_row_label_0_0" value="New Row"></label><div class="gar-actions"><button type="button" data-add-option>Add Option</button><button type="button" class="danger" data-remove-block>Remove Row</button></div></div><input type="hidden" name="gar_option_count_0_0" value="1" data-option-count><div data-gar-options>${option()}</div></div>`;
  const group = () => `<div class="gar-group" data-gar-group><div class="gar-subhead"><label>Group Name<input type="text" name="gar_group_name_0" value="New Group"></label><div class="gar-actions"><button type="button" data-add-row>Add Row</button><button type="button" class="danger" data-remove-block>Remove Group</button></div></div><input type="hidden" name="gar_row_count_0" value="1" data-row-count><div data-gar-rows>${row()}</div></div>`;
  const band = () => `<div class="gar-band" data-gar-band><label>Floor<input type="number" step="1" name="gar_band_floor_0" value="0"></label><label>Label<input type="text" name="gar_band_label_0" value="New Band"></label><label>Required Reviewer<input type="text" name="gar_band_reviewer_0"></label><button type="button" class="danger" data-remove-block>Remove</button></div>`;
  const renumber = () => {
    [...groups.children].forEach((g, gi) => {
      g.querySelector("input[name^='gar_group_name_']").name = `gar_group_name_${gi}`;
      const rs = [...g.querySelector("[data-gar-rows]").children];
      g.querySelector("[data-row-count]").name = `gar_row_count_${gi}`;
      g.querySelector("[data-row-count]").value = rs.length;
      rs.forEach((r, ri) => {
        r.querySelector("input[name^='gar_row_label_']").name = `gar_row_label_${gi}_${ri}`;
        const os = [...r.querySelector("[data-gar-options]").children];
        r.querySelector("[data-option-count]").name = `gar_option_count_${gi}_${ri}`;
        r.querySelector("[data-option-count]").value = os.length;
        os.forEach((o, oi) => {
          o.querySelector("input[name^='gar_option_label_']").name = `gar_option_label_${gi}_${ri}_${oi}`;
          o.querySelector("input[name^='gar_option_points_']").name = `gar_option_points_${gi}_${ri}_${oi}`;
          o.querySelector("input[name^='gar_option_no_go_']").name = `gar_option_no_go_${gi}_${ri}_${oi}`;
        });
      });
    });
    groupCount.value = groups.children.length;
    [...bands.children].forEach((b, bi) => {
      b.querySelector("input[name^='gar_band_floor_']").name = `gar_band_floor_${bi}`;
      b.querySelector("input[name^='gar_band_label_']").name = `gar_band_label_${bi}`;
      b.querySelector("input[name^='gar_band_reviewer_']").name = `gar_band_reviewer_${bi}`;
    });
    bandCount.value = bands.children.length;
  };
  form.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    if (button.matches("[data-add-group]")) groups.insertAdjacentHTML("beforeend", group());
    if (button.matches("[data-add-row]")) button.closest("[data-gar-group]").querySelector("[data-gar-rows]").insertAdjacentHTML("beforeend", row());
    if (button.matches("[data-add-option]")) button.closest("[data-gar-row]").querySelector("[data-gar-options]").insertAdjacentHTML("beforeend", option());
    if (button.matches("[data-add-band]")) bands.insertAdjacentHTML("beforeend", band());
    if (button.matches("[data-remove-block]")) button.closest("[data-gar-group], [data-gar-row], [data-gar-option], [data-gar-band]").remove();
    renumber();
  });
  renumber();
})();
</script>"""
    return f"""<form method="post" action="{action}">
  <div class="form-grid">
    <div class="field"><label>Name</label><input type="text" name="name" value="{escape(str(doc.get("name") or ""))}"></div>
    <div class="field"><label>Source</label><input type="text" name="source" value="{escape(str(doc.get("source") or ""))}"></div>
    <div class="field"><label>Updated By</label><input type="text" name="updated_by" value="{escape(str(doc.get("updated_by") or ""))}"></div>
    <div class="field"><label class="compact-check"><input type="checkbox" name="active" {active_checked}> Active</label></div>
  </div>
  <div class="field" style="margin-top:12px;"><label>Description</label><textarea name="description" rows="3">{escape(str(doc.get("description") or ""))}</textarea></div>
  <div class="gar-editor">
    <div class="gar-subhead"><h2>Groups / Rows / Options</h2><button type="button" data-add-group>Add Group</button></div>
    <input type="hidden" name="gar_group_count" value="{len(groups)}" data-group-count><div data-gar-groups>{"".join(group_blocks)}</div>
    <div class="gar-subhead"><h2>Score Bands</h2><button type="button" data-add-band>Add Band</button></div>
    <input type="hidden" name="gar_band_count" value="{len(bands)}" data-band-count><div data-gar-bands>{"".join(band_blocks)}</div>
  </div>
  <div class="form-actions"><button type="submit">{escape(submit_label)}</button></div>{script}</form>"""


def _form_html(spec: CollectionSpec, doc: dict[str, Any], *, action: str, submit_label: str) -> str:
    if spec.key == "gar-templates":
        return _gar_template_form_html(doc, action=action, submit_label=submit_label)
    combo_options: dict[str, list[tuple[str, str]]] = {}
    combo_depends: dict[str, str] = {}
    depmap_scripts = ""
    if spec.key == "personnel":
        org_rank_options = _personnel_org_rank_options()
        organization = str(doc.get("home_unit") or "").strip()
        combo_options["home_unit"] = org_rank_options["organization_options"]
        combo_options["rank"] = [(r, r) for r in org_rank_options["rank_by_org"].get(organization, [])]
        combo_options["emergency_blood_type"] = [(value, value) for value in _BLOOD_TYPE_OPTIONS]
        combo_options["contact_state"] = [(value, value) for value in _STATE_CODES]
        combo_depends["rank"] = "home_unit"
        depmap_json = json.dumps(org_rank_options["rank_by_org"], separators=(",", ":")).replace("</", "<\\/")
        depmap_scripts += f'<script type="application/json" data-combo-depmap-for="home_unit">{depmap_json}</script>'
    if spec.key in {"equipment", "vehicles", "aircraft"}:
        combo_options["organization"] = _organization_combo_options()
    if spec.key == "vehicles":
        from sarapp_db.api.routers import vehicles as vehicles_router

        type_options = [
            (str(row.get("id")), str(row.get("name") or row.get("id")))
            for row in vehicles_router.list_vehicle_types()
            if row.get("id") is not None
        ]
        status_options = [
            (str(row.get("id")), str(row.get("name") or row.get("id")))
            for row in vehicles_router.list_vehicle_statuses()
            if row.get("id") is not None
        ]
        if not type_options:
            type_options = [(value, value) for value in _VEHICLE_TYPE_OPTIONS]
        if not status_options:
            status_options = [(value, value) for value in _VEHICLE_STATUS_OPTIONS]
        combo_options["type_id"] = type_options
        combo_options["status_id"] = status_options
        combo_options["resource_type_id"] = _resource_type_combo_options()
    if spec.key == "aircraft":
        existing_aircraft = spec.list_fn()
        base_values = sorted({
            str(row.get("base") or "").strip()
            for row in existing_aircraft
            if str(row.get("base") or "").strip()
        })
        combo_options["type"] = [(value, value) for value in _AIRCRAFT_TYPE_OPTIONS]
        combo_options["status"] = [(value, value) for value in _AIRCRAFT_STATUS_OPTIONS]
        combo_options["fuel_type"] = [(value, value) for value in _AIRCRAFT_FUEL_OPTIONS]
        combo_options["med_config"] = [(value, value) for value in _AIRCRAFT_MED_CONFIG_OPTIONS]
        combo_options["base"] = [(value, value) for value in base_values]
    if spec.key == "rank-structures":
        from sarapp_db.api.routers import organizations as organizations_router

        org_types = [
            (str(t.get("int_id")), str(t.get("name")))
            for t in organizations_router.list_org_types(search="")
            if t.get("name")
        ]
        combo_options["organization_type_id"] = sorted(org_types, key=lambda t: t[1].lower())
    if spec.key == "ranks":
        from sarapp_db.api.routers import organizations as organizations_router

        rank_structures = [
            (str(r.get("int_id")), str(r.get("name")))
            for r in organizations_router.list_rank_structures(search="")
            if r.get("name")
        ]
        combo_options["rank_structure_id"] = sorted(rank_structures, key=lambda t: t[1].lower())
    if spec.key == "resource-types":
        from modules.admin.resource_types.models.resource_type_models import RESOURCE_CATEGORIES, RESOURCE_SOURCES

        combo_options["category"] = [(value, value) for value in RESOURCE_CATEGORIES]
        combo_options["source"] = [(value, value) for value in RESOURCE_SOURCES]
    if spec.key == "hospitals":
        combo_options["state"] = [(value, value) for value in _STATE_CODES]
    if spec.key == "hazard-types":
        from modules.admin.hazard_types.models.hazard_type_models import HAZARD_CATEGORIES

        combo_options["category"] = [(value, value) for value in HAZARD_CATEGORIES]
    if spec.key == "safety-analysis-templates":
        from modules.admin.hazard_types.models.hazard_type_models import SAFETY_SCENARIO_TYPES

        combo_options["scenario_type"] = [(value, value) for value in SAFETY_SCENARIO_TYPES]
    if spec.key in {"objective-templates", "strategy-templates"}:
        combo_options["priority"] = [(value, value) for value in ["Low", "Normal", "High", "Immediate"]]
    if spec.key == "objective-templates":
        combo_options["default_section"] = [
            (value, value)
            for value in ["", "Command", "Operations", "Planning", "Logistics", "Finance/Admin", "Safety"]
        ]
    if spec.key == "strategy-templates":
        from sarapp_db.api.routers import objective_templates as objective_templates_router

        objective_options = [
            (
                str(row.get("int_id_master") or row.get("int_id")),
                str(row.get("title") or row.get("code") or row.get("int_id_master") or row.get("int_id")),
            )
            for row in objective_templates_router.list_objective_templates(search="", include_archived=True, tag="")
            if row.get("int_id_master") is not None or row.get("int_id") is not None
        ]
        combo_options["objective_template_id"] = sorted(objective_options, key=lambda t: t[1].lower())
        combo_options["assignment_kind"] = [
            (value, value)
            for value in ["Ground", "Air", "UAS", "Medical", "Communications", "Logistics", "Other"]
        ]
    if spec.key == "radio-channels":
        combo_options["mode"] = [(value, value) for value in ["FM", "AM", "P25", "DMR", "NXDN", "LTE", "Other"]]
    if spec.key == "canned-comm-entries":
        combo_options["priority"] = [(value, value) for value in ["", "Low", "Normal", "High", "Urgent"]]
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
        if spec.key == "personnel" and field.name == "certifications":
            rows.append(
                f'<div class="field cert-field"><label>{escape(field.label)}</label>'
                f"{_personnel_certifications_picker_html(doc.get(field.name))}</div>"
            )
            continue
        if spec.key == "certification-types" and field.name == "tags":
            rows.append(
                f'<div class="field cert-field"><label>{escape(field.label)}</label>'
                f"{_certification_tags_picker_html(doc.get(field.name))}</div>"
            )
            continue
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
            f'<td><input type="number" step="1" name="sort_order_{index}" value="{escape(str(rank.get("sort_order") or rank.get("rank_order") or 0 if rank else ""))}"></td>'
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
            checked = raw.lower() in {"1", "true", "yes", "y", "on"}
            body[key] = int(checked) if field.value_type == "int" else checked
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
        visible_specs = sorted(
            (spec for spec in specs.values() if spec.key != "ranks"),
            key=lambda spec: spec.title.lower(),
        )
        items = "".join(
            f'<a class="collection-tile" href="{root_path}/gui/{escape(spec.key)}">{escape(spec.title)}'
            f'<span>{len(spec.fields)} editable fields</span></a>'
            for spec in visible_specs
        )
        body = f"""<section class="card"><div class="card-head"><div><h1>Master Catalog Collections</h1>
  <p class="card-subtitle">Central source for agency master catalogs, templates, and console access.</p></div></div>
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
        personnel_org_rank_options: dict[str, Any] | None = None
        organization_options: list[tuple[str, str]] = []
        vehicle_type_options: list[tuple[str, str]] = []
        vehicle_status_options: list[tuple[str, str]] = []
        if collection_key == "personnel":
            short_by_org_name = _org_short_name_by_name()
            personnel_org_rank_options = _personnel_org_rank_options()
            organization_options = personnel_org_rank_options["organization_options"]

            def list_cell_fn(row_doc: dict[str, Any], field_name: str, _short_by_name=short_by_org_name) -> Any:
                if field_name == "home_unit":
                    return _format_home_unit(row_doc.get("home_unit"), _short_by_name)
                return row_doc.get(field_name)
        elif collection_key in {"equipment", "vehicles", "aircraft"}:
            short_by_org_name = _org_short_name_by_name()
            organization_options = _organization_combo_options()
            if collection_key == "vehicles":
                from sarapp_db.api.routers import vehicles as vehicles_router

                vehicle_type_options = [
                    (str(row.get("id")), str(row.get("name") or row.get("id")))
                    for row in vehicles_router.list_vehicle_types()
                    if row.get("id") is not None
                ] or [(value, value) for value in _VEHICLE_TYPE_OPTIONS]
                vehicle_status_options = [
                    (str(row.get("id")), str(row.get("name") or row.get("id")))
                    for row in vehicles_router.list_vehicle_statuses()
                    if row.get("id") is not None
                ] or [(value, value) for value in _VEHICLE_STATUS_OPTIONS]

            def list_cell_fn(row_doc: dict[str, Any], field_name: str, _short_by_name=short_by_org_name) -> Any:
                if field_name == "organization":
                    return _format_organization(row_doc.get("organization"), _short_by_name)
                return row_doc.get(field_name)

        inline_fields = set(spec.inline_edit_fields or [])
        rows = []
        for doc in docs:
            record_id = doc.get(spec.record_field)
            display_doc = _form_doc(spec, doc)
            cells = []
            for f in shown_fields:
                display_value = list_cell_fn(display_doc, f.name) if list_cell_fn else display_doc.get(f.name, "")
                if f.name in inline_fields:
                    raw_value = display_doc.get(f.name, "")
                    editor_type = "checkbox" if f.input_type == "checkbox" else "select" if f.input_type in {"select", "select_fk"} else "text"
                    options: list[dict[str, str]] = []
                    if personnel_org_rank_options and f.name == "home_unit":
                        options = [
                            {"id": str(opt_id), "label": str(label)}
                            for opt_id, label in personnel_org_rank_options["organization_options"]
                        ]
                    elif f.name == "organization":
                        options = [
                            {"id": str(opt_id), "label": str(label)}
                            for opt_id, label in organization_options
                        ]
                        if raw_value and str(raw_value) not in {option["id"] for option in options}:
                            options.insert(0, {"id": str(raw_value), "label": str(raw_value)})
                    elif collection_key == "vehicles" and f.name == "type_id":
                        options = [
                            {"id": str(opt_id), "label": str(label)}
                            for opt_id, label in vehicle_type_options
                        ]
                        if raw_value and str(raw_value) not in {option["id"] for option in options}:
                            options.insert(0, {"id": str(raw_value), "label": str(raw_value)})
                    elif collection_key == "vehicles" and f.name == "status_id":
                        options = [
                            {"id": str(opt_id), "label": str(label)}
                            for opt_id, label in vehicle_status_options
                        ]
                        if raw_value and str(raw_value) not in {option["id"] for option in options}:
                            options.insert(0, {"id": str(raw_value), "label": str(raw_value)})
                    elif personnel_org_rank_options and f.name == "rank":
                        home_unit = str(display_doc.get("home_unit") or "").strip()
                        rank_options = personnel_org_rank_options["rank_by_org"].get(home_unit, [])
                        if raw_value and raw_value not in rank_options:
                            rank_options = [str(raw_value), *rank_options]
                        options = [{"id": str(value), "label": str(value)} for value in rank_options]
                    cells.append(
                        f'<td data-inline-td><span class="inline-cell" data-field="{escape(f.name)}" '
                        f'data-record="{record_id}" data-raw-value="{escape(_stringify(raw_value))}" '
                        f'data-editor="{editor_type}" data-options="{_json_attr(options)}">'
                        f"{_cell_html(display_value)}</span></td>"
                    )
                else:
                    cells.append(f"<td>{_cell_html(display_value)}</td>")
            cells_html = "".join(cells)
            row_href = f"{root_path}/gui/{collection_key}/{record_id}"
            row_attr = "" if inline_fields else f' data-row-href="{row_href}"'
            rows.append(
                f'<tr data-row{row_attr}><td class="record-cell">'
                f'<a class="button-link secondary row-edit-link" href="{row_href}">Edit</a></td>{cells_html}</tr>'
            )
        rows.append(
            f'<tr class="empty-row {"hidden" if docs else ""}"><td colspan="{len(shown_fields) + 1}">'
            "No matching records.</td></tr>"
        )
        inline_table_attrs = ""
        if inline_fields:
            inline_table_attrs = f' data-inline-collection="{escape(collection_key)}"'
            if collection_key == "personnel" and personnel_org_rank_options:
                inline_table_attrs += f' data-rank-by-org="{_json_attr(personnel_org_rank_options["rank_by_org"])}"'
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
    <table id="{table_id}"{inline_table_attrs}>
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
                spec.delete_fn(_record_route_arg(spec, str(record_id)))
        root_path = request.scope.get("root_path") or ""
        return RedirectResponse(f"{root_path}/gui/{collection_key}", status_code=303)

    @router.get("/gui/{collection_key}/{record_id}", response_class=HTMLResponse, response_model=None)
    def edit_form(request: Request, collection_key: str, record_id: str) -> Response:
        try:
            _require_session(settings, request)
        except HTTPException:
            return _redirect_login(request)
        spec = specs.get(collection_key)
        if spec is None:
            raise HTTPException(status_code=404, detail="Unknown collection")
        doc = spec.get_fn(_record_route_arg(spec, record_id))
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

    @router.post("/gui/{collection_key}/{record_id}/inline/{field_name}", response_model=None)
    async def inline_update_field(
        request: Request, collection_key: str, record_id: str, field_name: str
    ) -> Response:
        try:
            _require_session(settings, request)
        except HTTPException:
            return JSONResponse({"error": "login required"}, status_code=401)
        spec = specs.get(collection_key)
        if spec is None or field_name not in (spec.inline_edit_fields or []):
            return JSONResponse({"error": "field is not inline-editable"}, status_code=404)
        field = next((f for f in spec.fields if f.name == field_name), None)
        if field is None:
            return JSONResponse({"error": "unknown field"}, status_code=404)

        form = dict((await request.form()).items())
        raw = str(form.get("value", "")).strip()
        if field.input_type == "checkbox":
            value: Any = 1 if raw.lower() in {"1", "true", "yes", "y", "on"} else 0
        elif field.input_type == "list":
            value = _lines_to_list(raw)
        elif field.value_type == "int":
            value = int(raw) if raw else None
        elif field.value_type == "float":
            value = float(raw) if raw else None
        else:
            value = raw

        try:
            spec.update_fn(_record_route_arg(spec, record_id), {field_name: value})
        except HTTPException as exc:
            return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

        doc = spec.get_fn(_record_route_arg(spec, record_id))
        display_doc = _form_doc(spec, doc)
        display_value = display_doc.get(field_name, "")
        if collection_key == "personnel" and field_name == "home_unit":
            display_value = _format_home_unit(display_value, _org_short_name_by_name())
        if field_name == "organization":
            display_value = _format_organization(display_value, _org_short_name_by_name())

        return JSONResponse({"display": _stringify(display_value), "raw": _stringify(value)})

    @router.post("/gui/{collection_key}/{record_id}")
    async def update_record(request: Request, collection_key: str, record_id: str) -> Response:
        try:
            _require_session(settings, request)
        except HTTPException:
            return _redirect_login(request)
        spec = specs.get(collection_key)
        if spec is None:
            raise HTTPException(status_code=404, detail="Unknown collection")
        form = dict((await request.form()).items())
        body = _parse_form_body(spec, form)
        spec.update_fn(_record_route_arg(spec, record_id), body)
        root_path = request.scope.get("root_path") or ""
        return RedirectResponse(f"{root_path}/gui/{collection_key}/{record_id}", status_code=303)

    @router.post("/gui/{collection_key}/{record_id}/delete")
    def delete_record(request: Request, collection_key: str, record_id: str) -> Response:
        try:
            _require_session(settings, request)
        except HTTPException:
            return _redirect_login(request)
        spec = specs.get(collection_key)
        if spec is None or spec.delete_fn is None:
            raise HTTPException(status_code=404, detail="Unknown collection")
        spec.delete_fn(_record_route_arg(spec, record_id))
        root_path = request.scope.get("root_path") or ""
        return RedirectResponse(f"{root_path}/gui/{collection_key}", status_code=303)

    return router
