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


def _build_collection_specs() -> dict[str, CollectionSpec]:
    # Imported lazily (not at module import time) so this module can be
    # imported without sarapp_db being on the path yet in contexts that
    # never actually serve the GUI.
    from sarapp_db.api.routers import personnel as personnel_router
    from sarapp_db.api.routers import equipment as equipment_router
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

    specs = [
        CollectionSpec(
            key="personnel",
            title="Personnel",
            record_field="person_record",
            fields=[
                FieldSpec("name", "Name"),
                FieldSpec("person_id", "Person ID"),
                FieldSpec("primary_role", "Primary Role"),
                FieldSpec("rank", "Rank"),
                FieldSpec("callsign", "Callsign"),
                FieldSpec("organization", "Organization"),
                FieldSpec("phone", "Phone"),
                FieldSpec("email", "Email"),
                FieldSpec("is_medic", "Medic", input_type="checkbox"),
            ],
            # Called as plain Python functions, not through FastAPI's request
            # pipeline — any parameter whose real default is a
            # fastapi.params.Query/Body sentinel (not a plain Python value)
            # must be passed explicitly here, or the router function receives
            # the sentinel object itself instead of the value it stands in
            # for (it's truthy and has none of the real type's methods, so
            # this fails in confusing ways deep inside the function body).
            list_fn=lambda: personnel_router.list_personnel(search="", limit=200),
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
        ),
        CollectionSpec(
            key="equipment",
            title="Equipment",
            record_field="equipment_record",
            fields=[
                FieldSpec("name", "Name"),
                FieldSpec("equipment_id", "Equipment ID"),
                FieldSpec("type", "Type"),
                FieldSpec("serial_number", "Serial Number"),
                FieldSpec("status", "Status"),
                FieldSpec("organization", "Organization"),
            ],
            list_fn=lambda: equipment_router.list_equipment(search="", limit=200),
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
    main {{ padding:24px; max-width:1100px; margin:0 auto; }}
    a {{ color:#7db7ff; }}
    .card {{ border:1px solid #2d3a46; border-radius:6px; padding:16px; background:#151c23; margin-bottom:16px; }}
    table {{ width:100%; border-collapse:collapse; }}
    th, td {{ padding:8px; border-bottom:1px solid #2d3a46; text-align:left; vertical-align:top; }}
    th {{ color:#a7b6c5; font-weight:600; }}
    input[type=text], input[type=password], textarea {{ font:inherit; padding:8px 10px; border-radius:4px; border:1px solid #405160; background:#0f151b; color:#e8eef5; width:100%; box-sizing:border-box; }}
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
</body>
</html>"""
    return HTMLResponse(html)


def _field_input_html(field: FieldSpec, value: Any) -> str:
    safe_value = escape(str(value)) if value is not None else ""
    if field.input_type == "checkbox":
        checked = "checked" if value else ""
        return f'<input type="checkbox" name="{escape(field.name)}" {checked}>'
    if field.input_type == "textarea":
        return f'<textarea name="{escape(field.name)}" rows="3">{safe_value}</textarea>'
    return f'<input type="text" name="{escape(field.name)}" value="{safe_value}">'


def _form_html(spec: CollectionSpec, doc: dict[str, Any], *, action: str, submit_label: str) -> str:
    rows = []
    for field in spec.fields:
        rows.append(
            f'<label for="{escape(field.name)}">{escape(field.label)}</label>'
            f"{_field_input_html(field, doc.get(field.name))}"
        )
    return f"""<form method="post" action="{action}">{''.join(rows)}
  <p style="margin-top:16px;"><button type="submit">{escape(submit_label)}</button></p>
</form>"""


def _parse_form_body(spec: CollectionSpec, form: dict[str, str]) -> dict[str, Any]:
    body: dict[str, Any] = {}
    for field in spec.fields:
        if field.input_type == "checkbox":
            body[field.name] = field.name in form
        else:
            body[field.name] = form.get(field.name, "")
    return body


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
    export_rows = [spec.export_row_fn(row) if spec.export_row_fn else row for row in rows]
    headers = [spec.export_field_labels.get(key, key.title()) for key in spec.export_fields]
    if fmt == "xlsx":
        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.append(headers)
        for row in export_rows:
            sheet.append([_stringify(row.get(key)) for key in spec.export_fields])
        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in export_rows:
        writer.writerow([_stringify(row.get(key)) for key in spec.export_fields])
    return buffer.getvalue().encode("utf-8")


def _read_import_rows(spec: CollectionSpec, filename: str, data: bytes) -> list[dict[str, str]]:
    """Parse an uploaded CSV/XLSX export back into field-keyed row dicts.
    Matches each column header against a field's label or key
    (case-insensitive) — the same labels `_export_bytes` writes, so a file
    round-trips through either this page or the desktop panel's own
    Export/Import."""
    label_by_key = spec.export_field_labels
    key_by_header = {label.strip().lower(): key for key, label in label_by_key.items()}
    key_by_header.update({key.strip().lower(): key for key in spec.export_fields})

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
        if username != settings.admin_username or not hmac.compare_digest(
            hash_password(password), settings.admin_password_hash
        ):
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
        header_cells = "".join(f"<th>{escape(f.label)}</th>" for f in spec.fields)
        rows = []
        for doc in docs:
            record_id = doc.get(spec.record_field)
            cells = "".join(f"<td>{escape(str(doc.get(f.name, '')))}</td>" for f in spec.fields)
            rows.append(
                f'<tr><td><a href="{root_path}/gui/{collection_key}/{record_id}">{record_id}</a></td>{cells}</tr>'
            )
        body = f"""<section class="card"><h1>{escape(spec.title)}</h1>
  <p>
    <a href="{root_path}/gui/{collection_key}/new">+ New {escape(spec.title)}</a>
    &nbsp;|&nbsp;
    <a href="{root_path}/gui/{collection_key}/export?format=csv">Export CSV</a>
    &nbsp;|&nbsp;
    <a href="{root_path}/gui/{collection_key}/export?format=xlsx">Export XLSX</a>
    &nbsp;|&nbsp;
    <a href="{root_path}/gui/{collection_key}/import">Import</a>
  </p>
  <table><tr><th>{escape(spec.record_field)}</th>{header_cells}</tr>{''.join(rows)}</table>
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
                payload = spec.import_payload_fn(row) if spec.import_payload_fn else dict(row)
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
            spec, doc, action=f"{root_path}/gui/{collection_key}/{record_id}", submit_label="Save"
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
