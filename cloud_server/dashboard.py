"""Dashboard routes for the hosted SARApp cloud server."""

from __future__ import annotations

import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse

from cloud_server.backup import export_backup, import_backup, list_backups, save_uploaded_backup
from cloud_server.config import CloudSettings, hash_password
from cloud_server.runtime import ServerRuntime
from cloud_server.updater import start_update, update_state
from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.mongo_client import ping

_SESSION_COOKIE = "sarapp_cloud_session"
_SESSION_MAX_AGE_SECONDS = 12 * 60 * 60


def _sign(settings: CloudSettings, value: str) -> str:
    import hashlib

    return hmac.new(settings.session_secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def _session_value(settings: CloudSettings, username: str) -> str:
    expires = int((datetime.now(timezone.utc) + timedelta(seconds=_SESSION_MAX_AGE_SECONDS)).timestamp())
    payload = json.dumps({"u": username, "e": expires}, separators=(",", ":"))
    return f"{payload}.{_sign(settings, payload)}"


def _read_session(settings: CloudSettings, request: Request) -> str | None:
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


def _require_session(settings: CloudSettings, request: Request) -> str:
    username = _read_session(settings, request)
    if not username:
        raise HTTPException(status_code=401, detail="dashboard login required")
    return username


def _redirect_login(request: Request) -> RedirectResponse:
    root_path = request.scope.get("root_path") or ""
    return RedirectResponse(f"{root_path}/dashboard/login", status_code=303)


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
    main {{ padding:24px; max-width:1200px; margin:0 auto; }}
    a {{ color:#7db7ff; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:16px; }}
    .card {{ border:1px solid #2d3a46; border-radius:6px; padding:16px; background:#151c23; }}
    table {{ width:100%; border-collapse:collapse; }}
    th, td {{ padding:8px; border-bottom:1px solid #2d3a46; text-align:left; vertical-align:top; }}
    th {{ color:#a7b6c5; font-weight:600; }}
    input, button {{ font:inherit; padding:8px 10px; border-radius:4px; border:1px solid #405160; }}
    input {{ background:#0f151b; color:#e8eef5; }}
    button {{ background:#2f6fad; color:white; cursor:pointer; }}
    .danger {{ background:#8f3434; }}
    .muted {{ color:#9cadbd; }}
    nav a {{ margin-left:16px; }}
  </style>
</head>
<body>
  <header>
    <strong>SARApp Cloud Server DB</strong>
    <nav><a href="{root_path}/dashboard">Dashboard</a><a href="{root_path}/dashboard/connections">Connections</a><a href="{root_path}/dashboard/logs">Logs</a><a href="{root_path}/dashboard/backups">Backups</a><a href="{root_path}/dashboard/settings">Settings</a><a href="{root_path}/dashboard/logout">Logout</a></nav>
  </header>
  <main>{body}</main>
</body>
</html>"""
    return HTMLResponse(html)


def _active_connections() -> list[dict[str, Any]]:
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat(timespec="seconds")
    col = get_master_db()[MasterCollections.CLIENT_CONNECTIONS]
    mobile_connections = list(
        col.find(
            {"status": {"$ne": "revoked"}, "last_seen_at": {"$gte": cutoff}},
            {"_id": 0, "connection_token_hash": 0},
            sort=[("last_seen_at", -1)],
        )
    )
    return [*mobile_connections, *_active_desktop_sessions()]


def _active_desktop_sessions() -> list[dict[str, Any]]:
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat(timespec="seconds")
    db = get_master_db()
    sessions = db[MasterCollections.USER_SESSIONS]
    users = db[MasterCollections.USERS]
    personnel = db[MasterCollections.PERSONNEL]
    rows: list[dict[str, Any]] = []
    for session in sessions.find(
        {"ended_at": None, "status": {"$ne": "offline"}, "last_seen_at": {"$gte": cutoff}},
        {"_id": 0},
        sort=[("last_seen_at", -1)],
    ):
        user = users.find_one({"user_id": session.get("user_id")}, {"_id": 0}) or {}
        person = personnel.find_one({"person_record": session.get("person_record")}, {"_id": 0}) or {}
        rows.append(
            {
                "connection_kind": "desktop_session",
                "device_id": session.get("session_id"),
                "platform": "desktop",
                "device_name": session.get("device_name"),
                "display_name": session.get("display_name") or user.get("display_name"),
                "person_record": session.get("person_record"),
                "person_id": person.get("person_id") or session.get("username") or user.get("username"),
                "incident_id": session.get("incident_id"),
                "role": session.get("role"),
                "status": session.get("status"),
                "location_tracking_enabled": False,
                "last_seen_at": session.get("last_seen_at") or session.get("started_at"),
            }
        )
    return rows


def _firebase_status(settings: CloudSettings) -> dict[str, str]:
    path = settings.firebase_credentials_path
    if path and Path(path).is_file():
        return {"status": "configured", "path": path}
    return {"status": "not configured", "path": path}


def create_dashboard_router(settings: CloudSettings, runtime: ServerRuntime) -> APIRouter:
    router = APIRouter()

    @router.get("/dashboard/login", response_class=HTMLResponse)
    def login_page(request: Request) -> HTMLResponse:
        body = """
<div class="card" style="max-width:420px;margin:64px auto;">
  <h1>Server Login</h1>
  <form method="post">
    <p><input name="username" placeholder="Username" autocomplete="username" style="width:100%"></p>
    <p><input name="password" type="password" placeholder="Password" autocomplete="current-password" style="width:100%"></p>
    <p><button type="submit">Sign in</button></p>
  </form>
</div>"""
        return _page("Login", body, request)

    @router.post("/dashboard/login")
    async def login(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
    ) -> RedirectResponse:
        if username != settings.admin_username or not hmac.compare_digest(
            hash_password(password), settings.admin_password_hash
        ):
            return _redirect_login(request)
        response = RedirectResponse(f"{request.scope.get('root_path') or ''}/dashboard", status_code=303)
        response.set_cookie(
            _SESSION_COOKIE,
            _session_value(settings, username),
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=_SESSION_MAX_AGE_SECONDS,
        )
        return response

    @router.get("/dashboard/logout")
    def logout(request: Request) -> RedirectResponse:
        response = _redirect_login(request)
        response.delete_cookie(_SESSION_COOKIE)
        return response

    @router.get("/dashboard", response_class=HTMLResponse, response_model=None)
    def dashboard(request: Request) -> Response:
        try:
            _require_session(settings, request)
        except HTTPException:
            return _redirect_login(request)
        info = runtime.server_info()
        connections = _active_connections()
        traffic = runtime.requests.latest(20)
        updates = update_state()
        firebase = _firebase_status(settings)
        update_status = "running" if updates["running"] else "idle"
        update_body = (
            f"""<form method="post" action="{request.scope.get("root_path") or ""}/dashboard/update">
      <button type="submit">Run Update</button>
    </form>
    <p class="muted">Runs the fixed command configured by CLOUD_UPDATE_COMMAND.</p>"""
            if updates["enabled"]
            else "<p class=\"muted\">Set CLOUD_UPDATE_COMMAND to enable one-click updates.</p>"
        )
        body = f"""
<div class="grid">
  <section class="card"><h2>Status</h2>
    <p><strong>{escape(info["server_name"])}</strong></p>
    <p>Connect code: <strong>{escape(settings.connect_code)}</strong></p>
    <p>MongoDB: <strong>{"online" if ping() else "offline"}</strong></p>
    <p class="muted">Started {escape(info["started_at"])}</p>
  </section>
  <section class="card"><h2>Connections</h2>
    <p><strong>{len(connections)}</strong> active clients</p>
    <p><a href="{request.scope.get("root_path") or ""}/dashboard/connections">View active connections</a></p>
  </section>
  <section class="card"><h2>Container Updates</h2>
    <p>Status: <strong>{escape(update_status)}</strong></p>
    <p class="muted">Last return code: {escape(str(updates["last_returncode"]))}</p>
    {update_body}
  </section>
  <section class="card"><h2>Firebase</h2>
    <p>Status: <strong>{escape(firebase["status"])}</strong></p>
    <p class="muted">{escape(firebase["path"])}</p>
    <p><a href="{request.scope.get("root_path") or ""}/dashboard/settings">Manage settings</a></p>
  </section>
</div>
<section class="card" style="margin-top:16px;"><h2>Update Log</h2>
  <pre style="white-space:pre-wrap;max-height:260px;overflow:auto;">{escape(chr(10).join(updates["last_output"][-80:]))}</pre>
</section>
<section class="card" style="margin-top:16px;"><h2>Recent API Traffic</h2>
  <table><tr><th>Time</th><th>Client</th><th>Request</th><th>Status</th><th>ms</th></tr>
  {"".join(f"<tr><td>{escape(str(r.get('timestamp','')))}</td><td>{escape(str(r.get('client','')))}</td><td>{escape(str(r.get('method','')))} {escape(str(r.get('path','')))}</td><td>{escape(str(r.get('status','')))}</td><td>{escape(str(r.get('duration_ms','')))}</td></tr>" for r in traffic)}
  </table>
</section>"""
        return _page("Dashboard", body, request)

    @router.post("/dashboard/update")
    def run_update(request: Request) -> RedirectResponse:
        _require_session(settings, request)
        try:
            start_update()
        except RuntimeError:
            pass
        return RedirectResponse(f"{request.scope.get('root_path') or ''}/dashboard", status_code=303)

    @router.get("/dashboard/connections", response_class=HTMLResponse, response_model=None)
    def connections_page(request: Request) -> Response:
        try:
            _require_session(settings, request)
        except HTTPException:
            return _redirect_login(request)
        rows = _active_connections()
        body = f"""
<section class="card"><h1>Active Connections</h1>
  <table><tr><th>Type</th><th>Device</th><th>Person</th><th>Platform</th><th>Incident</th><th>Team</th><th>Last Seen</th></tr>
  {"".join(f"<tr><td>{escape(str(r.get('connection_kind') or 'client'))}</td><td>{escape(str(r.get('device_name') or r.get('device_id') or ''))}</td><td>{escape(str(r.get('display_name') or r.get('person_id') or r.get('person_record') or ''))}</td><td>{escape(str(r.get('platform') or ''))}</td><td>{escape(str(r.get('incident_id') or ''))}</td><td>{escape(str(r.get('team_name') or r.get('team_id') or ''))}</td><td>{escape(str(r.get('last_seen_at') or ''))}</td></tr>" for r in rows)}
  </table>
</section>"""
        return _page("Connections", body, request)

    @router.get("/dashboard/logs", response_class=HTMLResponse, response_model=None)
    def logs_page(request: Request) -> Response:
        try:
            _require_session(settings, request)
        except HTTPException:
            return _redirect_login(request)
        rows = runtime.logs.latest(500)
        body = f"""
<section class="card"><h1>Server Logs</h1>
  <pre style="white-space:pre-wrap;max-height:70vh;overflow:auto;">{escape(chr(10).join(reversed(rows)))}</pre>
</section>"""
        return _page("Logs", body, request)

    @router.get("/dashboard/settings", response_class=HTMLResponse, response_model=None)
    def settings_page(request: Request) -> Response:
        try:
            _require_session(settings, request)
        except HTTPException:
            return _redirect_login(request)
        firebase = _firebase_status(settings)
        body = f"""
<section class="card"><h1>Settings</h1>
  <h2>Firebase Push Notifications</h2>
  <p>Status: <strong>{escape(firebase["status"])}</strong></p>
  <p class="muted">Credential path: {escape(firebase["path"])}</p>
  <form method="post" enctype="multipart/form-data" action="{request.scope.get("root_path") or ""}/dashboard/settings/firebase">
    <p><input type="file" name="file" accept=".json" required></p>
    <p><button type="submit">Upload Firebase Key</button></p>
  </form>
</section>"""
        return _page("Settings", body, request)

    @router.post("/dashboard/settings/firebase")
    async def upload_firebase_key(request: Request, file: UploadFile = File(...)) -> RedirectResponse:
        _require_session(settings, request)
        destination = Path(settings.firebase_credentials_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = await file.read()
        json.loads(data.decode("utf-8"))
        destination.write_bytes(data)
        os.environ["SARAPP_FIREBASE_CREDENTIALS_PATH"] = str(destination)
        return RedirectResponse(f"{request.scope.get('root_path') or ''}/dashboard/settings", status_code=303)

    @router.get("/dashboard/backups", response_class=HTMLResponse, response_model=None)
    def backups_page(request: Request) -> Response:
        try:
            _require_session(settings, request)
        except HTTPException:
            return _redirect_login(request)
        rows = list_backups(settings.backup_dir)
        body = f"""
<div class="grid">
  <section class="card"><h2>Export</h2>
    <form method="post" action="{request.scope.get("root_path") or ""}/dashboard/backups/export">
      <button type="submit">Create and Download Backup</button>
    </form>
  </section>
  <section class="card"><h2>Import To New Databases</h2>
    <form method="post" enctype="multipart/form-data" action="{request.scope.get("root_path") or ""}/dashboard/backups/import">
      <p><input type="file" name="file" accept=".zip" required></p>
      <p><input name="label" placeholder="New database suffix" required></p>
      <p><button type="submit">Upload and Import</button></p>
    </form>
  </section>
</div>
<section class="card" style="margin-top:16px;"><h2>Saved Backups</h2>
  <table><tr><th>Name</th><th>Size</th><th>Updated</th></tr>
  {"".join(f"<tr><td>{escape(r['name'])}</td><td>{r['size']}</td><td>{escape(r['updated_at'])}</td></tr>" for r in rows)}
  </table>
</section>"""
        return _page("Backups", body, request)

    @router.post("/dashboard/backups/export")
    def export_backup_route(request: Request) -> StreamingResponse:
        _require_session(settings, request)
        filename, data = export_backup(server_id=settings.server_id, connect_code=settings.connect_code)
        save_uploaded_backup(data, settings.backup_dir, filename)
        return StreamingResponse(
            iter([data]),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.post("/dashboard/backups/import")
    async def import_backup_route(
        request: Request,
        file: UploadFile = File(...),
        label: str = Form(...),
    ) -> Response:
        try:
            _require_session(settings, request)
        except HTTPException:
            return _redirect_login(request)
        data = await file.read()
        save_uploaded_backup(data, settings.backup_dir, file.filename or "uploaded.zip")
        result = import_backup(data, label=label)
        rows = "".join(
            f"<tr><td>{escape(r['source'])}</td><td>{escape(r['target'])}</td></tr>"
            for r in result["restored"]
        )
        body = f"<section class=\"card\"><h1>Import Complete</h1><table><tr><th>Source</th><th>New DB</th></tr>{rows}</table></section>"
        return _page("Import Complete", body, request)

    @router.get("/api/cloud/dashboard/status")
    def dashboard_status(request: Request) -> dict[str, Any]:
        _require_session(settings, request)
        return {
            "server": runtime.server_info(),
            "mongo_online": ping(),
            "active_connections": len(_active_connections()),
            "recent_requests": runtime.requests.latest(20),
            "update": update_state(),
        }

    return router

