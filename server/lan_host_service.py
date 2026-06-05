from __future__ import annotations

import asyncio
import logging
import socket
import sqlite3
import threading
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from models.database import get_incident_by_number
from modules.communications.traffic_log.services import CommsLogService
from modules.operations.data.repository import (
    fetch_task_rows,
    fetch_team_assignment_rows,
    set_task_status,
    set_team_status,
)
from notifications.models.notification import Notification
from notifications.services import get_notifier
from shared import lan_events
from utils import incident_context, incident_storage
from utils.state import AppState

logger = logging.getLogger(__name__)


class _SocketHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    @property
    def count(self) -> int:
        return len(self._clients)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self._clients:
                self._clients.remove(websocket)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        async with self._lock:
            peers = list(self._clients)
        stale: list[WebSocket] = []
        for ws in peers:
            try:
                await ws.send_json(payload)
            except Exception:
                stale.append(ws)
        if stale:
            async with self._lock:
                for ws in stale:
                    self._clients.discard(ws)


class LanHostService:
    def __init__(self) -> None:
        self._app = FastAPI(title="IMA LAN Host")
        self._hub = _SocketHub()
        self._server = None
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._host = "0.0.0.0"
        self._port = 8000
        self._is_running = False
        self._register_routes()

    @property
    def app(self) -> FastAPI:
        return self._app

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def connected_clients(self) -> int:
        return self._hub.count

    def active_incident(self) -> str | None:
        active = AppState.get_active_incident()
        return None if active is None else str(active)

    def lan_ipv4_addresses(self) -> list[str]:
        found: list[str] = []
        try:
            for fam, _, _, _, sockaddr in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                if fam != socket.AF_INET:
                    continue
                ip = str(sockaddr[0])
                if ip.startswith("127."):
                    continue
                if ip not in found:
                    found.append(ip)
        except Exception:
            pass
        if not found:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                s.close()
                if ip and not ip.startswith("127."):
                    found.append(ip)
            except Exception:
                pass
        return found

    def primary_lan_ip(self) -> str:
        all_ips = self.lan_ipv4_addresses()
        if all_ips:
            return all_ips[0]
        return "127.0.0.1"

    def start(self, *, host: str = "0.0.0.0", port: int = 8000) -> tuple[bool, str]:
        active = self.active_incident()
        if not active:
            return False, "Cannot start host mode without an active incident."
        if self._is_running:
            return True, "Host mode already running."
        self._host = str(host)
        self._port = int(port)
        try:
            import uvicorn
        except Exception as exc:
            return False, f"uvicorn is required for host mode: {exc}"

        def _run() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            config = uvicorn.Config(self._app, host=self._host, port=self._port, log_level="warning")
            self._server = uvicorn.Server(config)
            self._is_running = True
            try:
                self._server.run()
            finally:
                self._is_running = False

        self._thread = threading.Thread(target=_run, name="lan-host-service", daemon=True)
        self._thread.start()
        return True, "Host mode started."

    def stop(self) -> None:
        if not self._is_running:
            return
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._thread = None
        self._server = None
        self._is_running = False

    def broadcast_event(self, event_type: str, payload: dict[str, Any]) -> None:
        if not self._is_running or self._loop is None:
            return
        event = lan_events.make_event(event_type, payload)
        fut = asyncio.run_coroutine_threadsafe(self._hub.broadcast(event), self._loop)
        try:
            fut.result(timeout=1.0)
        except Exception:
            logger.debug("LAN broadcast failed", exc_info=True)

    def build_bootstrap(self) -> dict[str, Any]:
        incident_number = self.active_incident()
        incident_meta = get_incident_by_number(incident_number) if incident_number else None
        comms_service = CommsLogService(incident_id=incident_number)
        comms_entries = [e.to_record() for e in comms_service.list_entries()[:250]]
        alerts = get_notifier().recent(limit=100)
        return {
            "incident": {
                "number": incident_number,
                "name": (incident_meta or {}).get("name") if incident_meta else incident_number,
                "type": (incident_meta or {}).get("type") if incident_meta else "",
            },
            "teams": fetch_team_assignment_rows(),
            "tasks": fetch_task_rows(),
            "comms": comms_entries,
            "alerts": alerts,
            "master_lookups": {
                "channels": comms_service.list_channels(),
            },
        }

    def _session_payload(self) -> dict[str, Any]:
        incident_number = self.active_incident()
        incident_meta = get_incident_by_number(incident_number) if incident_number else None
        return {
            "hosting": bool(self._is_running),
            "incident": {
                "number": incident_number,
                "name": (incident_meta or {}).get("name") if incident_meta else incident_number,
            },
            "host_ip": self.primary_lan_ip(),
            "lan_ips": self.lan_ipv4_addresses(),
            "port": self._port,
            "clients": self.connected_clients,
            "master_db": str(incident_storage.master_db_path()),
            "incident_db": str(incident_context.get_active_incident_db_path()) if incident_number else None,
        }

    def _register_routes(self) -> None:
        @self._app.get("/lan/session")
        async def lan_session() -> dict[str, Any]:
            return self._session_payload()

        @self._app.get("/lan/bootstrap")
        async def lan_bootstrap() -> dict[str, Any]:
            payload = self.build_bootstrap()
            return payload

        @self._app.post("/lan/team/update")
        async def lan_team_update(body: dict[str, Any]) -> dict[str, Any]:
            team_id = int(body.get("team_id"))
            status = str(body.get("status") or "")
            set_team_status(team_id, status)
            rows = fetch_team_assignment_rows()
            team_row = next((r for r in rows if int(r.get("team_id") or -1) == team_id), None)
            event_type = lan_events.TEAM_STATUS_CHANGED if body.get("status_only", True) else lan_events.TEAM_UPDATED
            self.broadcast_event(event_type, {"team_id": team_id, "status": status, "team": team_row})
            return {"ok": True, "team": team_row}

        @self._app.post("/lan/task/update")
        async def lan_task_update(body: dict[str, Any]) -> dict[str, Any]:
            task_id = int(body.get("task_id"))
            status = str(body.get("status") or "")
            set_task_status(task_id, status)
            rows = fetch_task_rows()
            task_row = next((r for r in rows if int(r.get("id") or -1) == task_id), None)
            event_type = lan_events.TASK_STATUS_CHANGED if body.get("status_only", True) else lan_events.TASK_UPDATED
            self.broadcast_event(event_type, {"task_id": task_id, "status": status, "task": task_row})
            return {"ok": True, "task": task_row}

        @self._app.post("/lan/comms/create")
        async def lan_comms_create(body: dict[str, Any]) -> dict[str, Any]:
            service = CommsLogService(incident_id=self.active_incident())
            entry = service.create_entry(body)
            payload = entry.to_record()
            self.broadcast_event(lan_events.COMMS_CREATED, {"entry": payload})
            return {"ok": True, "entry": payload}

        @self._app.post("/lan/alert/create")
        async def lan_alert_create(body: dict[str, Any]) -> dict[str, Any]:
            note = Notification(
                title=str(body.get("title") or "Alert"),
                message=str(body.get("message") or ""),
                severity=str(body.get("severity") or "warning"),
                source=str(body.get("source") or "LAN"),
                entity_type=body.get("entity_type"),
                entity_id=str(body.get("entity_id")) if body.get("entity_id") is not None else None,
            )
            get_notifier().notify(note)
            alert = get_notifier().recent(limit=1)
            payload = alert[0] if alert else body
            self.broadcast_event(lan_events.ALERT_CREATED, {"alert": payload})
            return {"ok": True, "alert": payload}

        @self._app.websocket("/lan/ws")
        async def lan_ws(websocket: WebSocket) -> None:
            await self._hub.connect(websocket)
            await self._hub.broadcast(
                lan_events.make_event(lan_events.CONNECTION_STATE, {"clients": self.connected_clients, "state": "connected"})
            )
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                await self._hub.disconnect(websocket)
                await self._hub.broadcast(
                    lan_events.make_event(lan_events.CONNECTION_STATE, {"clients": self.connected_clients, "state": "disconnected"})
                )


lan_host_service = LanHostService()
