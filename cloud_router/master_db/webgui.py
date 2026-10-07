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
    value_type: str = "str"  # "str" | "int" | "bool"


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
    org_names: list[str] = []
    for org in orgs:
        name = str(org.get("name") or "").strip()
        if not name or not int(org.get("is_active", 1)):
            continue
        org_names.append(name)
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
        "organizations": sorted(org_names, key=str.lower),
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
            fields=[
                FieldSpec("name", "Name"),
                FieldSpec("description", "Description", input_type="textarea"),
                FieldSpec("organization_type_id", "Organization Type ID", value_type="int"),
                FieldSpec("is_template", "Template", input_type="checkbox", value_type="int"),
                FieldSpec("is_system_template", "System Template", input_type="checkbox", value_type="int"),
                FieldSpec("sort_order", "Sort Order", value_type="int"),
                FieldSpec("is_active", "Active", input_type="checkbox", value_type="int"),
            ],
            list_fn=lambda: organizations_router.list_rank_structures(search=""),
            get_fn=organizations_router.get_rank_structure,
            create_fn=organizations_router.create_rank_structure,
            update_fn=organizations_router.update_rank_structure,
            delete_fn=organizations_router.delete_rank_structure,
        ),
        CollectionSpec(
            key="organizations",
            title="Organizations",
            record_field="int_id",
            fields=[
                FieldSpec("name", "Name"),
                FieldSpec("short_name", "Short Name"),
                FieldSpec("parent_organization_id", "Parent Organization ID", value_type="int"),
                FieldSpec("organization_type_id", "Organization Type ID", value_type="int"),
                FieldSpec("default_rank_structure_id", "Default Rank Structure ID", value_type="int"),
                FieldSpec("callsign_prefix", "Callsign Prefix"),
                FieldSpec("external_id", "External ID"),
                FieldSpec("notes", "Notes", input_type="textarea"),
                FieldSpec("sort_order", "Sort Order", value_type="int"),
                FieldSpec("is_active", "Active", input_type="checkbox", value_type="int"),
            ],
            list_fn=lambda: organizations_router.list_organizations(search=""),
            get_fn=organizations_router.get_organization,
            create_fn=organizations_router.create_organization,
            update_fn=organizations_router.update_organization,
            delete_fn=organizations_router.delete_organization,
        ),
        CollectionSpec(
            key="ranks",
            title="Ranks",
            record_field="int_id",
            fields=[
                FieldSpec("rank_structure_id", "Rank Structure ID", value_type="int"),
                FieldSpec("rank_code", "Rank Code"),
                FieldSpec("rank_name", "Rank Name"),
                FieldSpec("short_display", "Short Display"),
                FieldSpec("sort_order", "Sort Order", value_type="int"),
                FieldSpec("is_active", "Active", input_type="checkbox", value_type="int"),
            ],
            list_fn=lambda: organizations_router.list_ranks(structure_id=None, search=""),
            get_fn=organizations_router.get_rank,
            create_fn=organizations_router.create_rank,
            update_fn=organizations_router.update_rank,
            delete_fn=organizations_router.delete_rank,
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
    body {{ margin:0; font-family:Segoe UI, Arial, sans-serif; background:#101418; color:#e8eef5; }}
    header {{ display:flex; align-items:center; justify-content:space-between; padding:16px 24px; background:#17202a; border-bottom:1px solid #2d3a46; }}
    main {{ padding:24px; max-width:1600px; margin:0 auto; }}
    a {{ color:#7db7ff; }}
    .card {{ border:1px solid #2d3a46; border-radius:6px; padding:16px; background:#151c23; margin-bottom:16px; }}
    .grid-toolbar {{ display:flex; flex-wrap:wrap; gap:12px; align-items:center; justify-content:space-between; margin:12px 0; }}
    .grid-actions a {{ margin-right:12px; }}
    .grid-search {{ max-width:420px; }}
    .table-wrap {{ overflow:auto; border:1px solid #2d3a46; border-radius:6px; max-height:70vh; }}
    table {{ width:100%; border-collapse:separate; border-spacing:0; min-width:900px; }}
    th, td {{ padding:8px; border-bottom:1px solid #2d3a46; text-align:left; vertical-align:top; }}
    th {{ color:#a7b6c5; font-weight:600; position:sticky; top:0; background:#17202a; z-index:1; user-select:none; }}
    th.sortable {{ cursor:pointer; }}
    th.sortable::after {{ content:""; display:inline-block; margin-left:6px; color:#7db7ff; }}
    th.sortable[data-dir="asc"]::after {{ content:"▲"; }}
    th.sortable[data-dir="desc"]::after {{ content:"▼"; }}
    tr.hidden {{ display:none; }}
    .record-cell {{ white-space:nowrap; }}
    .row-resizer {{ display:inline-block; width:10px; height:16px; margin-left:8px; cursor:ns-resize; vertical-align:middle; border-top:2px solid #405160; border-bottom:2px solid #405160; }}
    .empty-row td {{ color:#9cadbd; text-align:center; padding:18px; }}
    input[type=text], input[type=password], textarea, select {{ font:inherit; padding:8px 10px; border-radius:4px; border:1px solid #405160; background:#0f151b; color:#e8eef5; width:100%; box-sizing:border-box; }}
    select:disabled {{ color:#74808d; background:#141a20; cursor:not-allowed; }}
    label {{ display:block; margin:10px 0 4px; color:#a7b6c5; }}
    button {{ font:inherit; padding:8px 14px; border-radius:4px; border:1px solid #405160; background:#2f6fad; color:white; cursor:pointer; }}
    .danger {{ background:#8f3434; }}
    .muted {{ color:#9cadbd; }}
    nav a {{ margin-left:16px; }}
    form.inline {{ display:inline; }}
  </style>
</head>
<body>
  <header>
    <strong>SARApp Central Master Database</strong>
    <nav><a href="{root_path}/gui">Collections</a><a href="{root_path}/gui/logout">Logout</a></nav>
  </header>
  <main>{body}</main>
<script>
(function() {{
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

  document.querySelectorAll(".row-resizer").forEach((handle) => {{
    handle.addEventListener("mousedown", (event) => {{
      event.preventDefault();
      const row = handle.closest("tr");
      const startY = event.clientY;
      const startHeight = row.getBoundingClientRect().height;
      function move(moveEvent) {{
        row.style.height = Math.max(32, startHeight + moveEvent.clientY - startY) + "px";
      }}
      function up() {{
        document.removeEventListener("mousemove", move);
        document.removeEventListener("mouseup", up);
      }}
      document.addEventListener("mousemove", move);
      document.addEventListener("mouseup", up);
    }});
  }});

  document.querySelectorAll("[data-org-select]").forEach((orgSelect) => {{
    const form = orgSelect.closest("form");
    const rankSelect = form ? form.querySelector("[data-rank-select]") : null;
    if (!rankSelect) return;
    let rankMap = {{}};
    try {{
      rankMap = JSON.parse(orgSelect.dataset.rankMap || "{{}}");
    }} catch (err) {{
      rankMap = {{}};
    }}
    function refreshRanks() {{
      const current = rankSelect.value || rankSelect.dataset.current || "";
      const ranks = rankMap[orgSelect.value] || [];
      rankSelect.innerHTML = '<option value=""></option>';
      for (const rank of ranks) {{
        const option = document.createElement("option");
        option.value = rank;
        option.textContent = rank;
        if (rank === current) option.selected = true;
        rankSelect.appendChild(option);
      }}
      rankSelect.disabled = !orgSelect.value;
      if (!ranks.includes(current)) rankSelect.value = "";
      rankSelect.dataset.current = rankSelect.value;
    }}
    orgSelect.addEventListener("change", () => {{
      rankSelect.dataset.current = "";
      refreshRanks();
    }});
    refreshRanks();
  }});
}})();
</script>
</body>
</html>"""
    return HTMLResponse(html)


def _field_input_html(
    field: FieldSpec,
    value: Any,
    *,
    select_options: dict[str, list[str]] | None = None,
    select_data: dict[str, str] | None = None,
) -> str:
    safe_value = escape(str(value)) if value is not None else ""
    if field.input_type == "checkbox":
        checked = "checked" if str(value).strip().lower() in {"1", "true", "yes", "y", "on"} else ""
        return f'<input type="checkbox" name="{escape(field.name)}" {checked}>'
    if field.input_type == "select":
        options = list((select_options or {}).get(field.name, []))
        if safe_value and str(value) not in options:
            options.insert(0, str(value))
        disabled = " disabled" if field.name == "rank" and not options and not str(value or "").strip() else ""
        data_attrs = "".join(
            f' data-{escape(key)}="{escape(val)}"' for key, val in (select_data or {}).items()
        )
        option_html = ['<option value=""></option>']
        option_html.extend(
            f'<option value="{escape(option)}"{" selected" if option == str(value or "") else ""}>{escape(option)}</option>'
            for option in options
        )
        return f'<select name="{escape(field.name)}"{disabled}{data_attrs}>{"".join(option_html)}</select>'
    if field.input_type == "textarea":
        return f'<textarea name="{escape(field.name)}" rows="3">{safe_value}</textarea>'
    return f'<input type="text" name="{escape(field.name)}" value="{safe_value}">'


def _cell_html(value: Any) -> str:
    text = _stringify(value)
    if len(text) > 180:
        text = f"{text[:177]}..."
    return escape(text)


def _form_html(spec: CollectionSpec, doc: dict[str, Any], *, action: str, submit_label: str) -> str:
    select_options: dict[str, list[str]] = {}
    select_data_by_field: dict[str, dict[str, str]] = {}
    if spec.key == "personnel":
        org_rank_options = _personnel_org_rank_options()
        organization = str(doc.get("home_unit") or "").strip()
        select_options["home_unit"] = org_rank_options["organizations"]
        select_options["rank"] = org_rank_options["rank_by_org"].get(organization, [])
        rank_by_org_json = json.dumps(org_rank_options["rank_by_org"], separators=(",", ":"))
        select_data_by_field["home_unit"] = {"org-select": "1", "rank-map": rank_by_org_json}
        select_data_by_field["rank"] = {"rank-select": "1", "current": str(doc.get("rank") or "")}

    rows = []
    for field in spec.fields:
        rows.append(
            f'<label for="{escape(field.name)}">{escape(field.label)}</label>'
            f"{_field_input_html(field, doc.get(field.name), select_options=select_options, select_data=select_data_by_field.get(field.name))}"
        )
    return f"""<form method="post" action="{action}">{''.join(rows)}
  <p style="margin-top:16px;"><button type="submit">{escape(submit_label)}</button></p>
</form>"""


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
        else:
            body[field.name] = form.get(field.name, "")
    return body


def _coerce_import_payload(spec: CollectionSpec, row: dict[str, str]) -> dict[str, Any]:
    if spec.import_payload_fn is not None:
        return spec.import_payload_fn(row)

    body: dict[str, Any] = {}
    field_by_name = {field.name: field for field in spec.fields}
    for key in _field_keys(spec):
        field = field_by_name.get(key)
        raw = str(row.get(key, "")).strip()
        if not raw:
            continue
        if field and field.input_type == "checkbox":
            body[key] = 1 if raw.lower() in {"1", "true", "yes", "y", "on"} else 0
        elif field and field.value_type == "int":
            body[key] = int(raw)
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
<div class="card" style="max-width:420px;margin:64px auto;">
  <h1>Central Master Database</h1>
  <form method="post">
    <label>Username</label><input type="text" name="username" autocomplete="username">
    <label>Password</label><input type="password" name="password" autocomplete="current-password">
    <p style="margin-top:16px;"><button type="submit">Sign in</button></p>
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
        items = "".join(
            f'<tr><td><a href="{root_path}/gui/{escape(spec.key)}">{escape(spec.title)}</a></td></tr>'
            for spec in specs.values()
        )
        body = f"""<section class="card"><h1>Master Catalog Collections</h1>
  <table>{items}</table>
  <p class="muted">More collections are added to this GUI incrementally — see backlog.md.</p>
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
        header_cells = "".join(f'<th class="sortable">{escape(f.label)}</th>' for f in spec.fields)
        rows = []
        for doc in docs:
            record_id = doc.get(spec.record_field)
            display_doc = _form_doc(spec, doc)
            cells = "".join(f"<td>{_cell_html(display_doc.get(f.name, ''))}</td>" for f in spec.fields)
            rows.append(
                f'<tr data-row><td class="record-cell"><a href="{root_path}/gui/{collection_key}/{record_id}">{record_id}</a>'
                f'<span class="row-resizer" title="Drag to resize row"></span></td>{cells}</tr>'
            )
        rows.append(
            f'<tr class="empty-row {"hidden" if docs else ""}"><td colspan="{len(spec.fields) + 1}">'
            "No matching records.</td></tr>"
        )
        body = f"""<section class="card"><h1>{escape(spec.title)}</h1>
  <div class="grid-toolbar">
    <div class="grid-actions">
      <a href="{root_path}/gui/{collection_key}/new">+ New {escape(spec.title)}</a>
      <a href="{root_path}/gui/{collection_key}/export?format=csv">Export CSV</a>
      <a href="{root_path}/gui/{collection_key}/export?format=xlsx">Export XLSX</a>
      <a href="{root_path}/gui/{collection_key}/import">Import</a>
    </div>
    <input class="grid-search" type="text" data-grid-search="{table_id}" placeholder="Search this table">
  </div>
  <div class="table-wrap">
    <table id="{table_id}">
      <thead><tr><th class="sortable">{escape(spec.record_field)}</th>{header_cells}</tr></thead>
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
        body = f'<section class="card"><h1>New {escape(spec.title)}</h1>{form}</section>'
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
        body = f"""<section class="card"><h1>Import {escape(spec.title)}</h1>
  <p class="muted">Upload a CSV or XLSX file exported from this page or the desktop Edit-menu panel — same columns, matched by header.</p>
  <form method="post" enctype="multipart/form-data" action="{root_path}/gui/{collection_key}/import">
    <input type="file" name="file" accept=".csv,.xlsx" required>
    <p style="margin-top:16px;"><button type="submit">Import</button></p>
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
  <p><a href="{root_path}/gui/{collection_key}">Back to {escape(spec.title)}</a></p>
</section>"""
        return _page("Import Complete", body, request)

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
            f"""<form class="inline" method="post" action="{root_path}/gui/{collection_key}/{record_id}/delete">
  <button type="submit" class="danger">Delete</button>
</form>"""
            if spec.delete_fn is not None
            else ""
        )
        body = f'<section class="card"><h1>{escape(spec.title)} {record_id}</h1>{form}{delete_button}</section>'
        return _page(f"Edit {spec.title}", body, request)

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
