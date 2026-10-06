"""SARApp cloud router runtime.

Runs as a headless service. Unlike a LAN server, this process has no MongoDB
connection and runs no ``sarapp_db`` routers — it is a stateless reverse
proxy that forwards field-device traffic to whichever LAN server has
registered a reverse tunnel under a given connect code. See
``Design Documents/Instructions/cloud_router_architecture.md``.
"""

from __future__ import annotations

import socket
import threading
import uuid
from typing import Any

import uvicorn

from networking.server_info import (
    DEFAULT_SERVER_PORT,
    SARAPP_VERSION,
    ServerInfo,
    ServerStatus,
    utc_now,
)
from router.app import create_router_app


def _default_server_id() -> str:
    return f"sarapp-cloud-router-{socket.gethostname()}-{uuid.uuid4().hex[:8]}"


class SARAppServerManager:
    """Owns the cloud router's uvicorn process."""

    def __init__(
        self,
        *,
        host: str = "0.0.0.0",
        port: int = DEFAULT_SERVER_PORT,
        server_id: str | None = None,
        server_name: str | None = None,
        version: str = SARAPP_VERSION,
    ) -> None:
        self.host = host
        self.port = port
        self.server_info = ServerInfo(
            server_id=server_id or _default_server_id(),
            server_name=server_name or f"SARApp Cloud Router on {socket.gethostname()}",
            version=version,
            status=ServerStatus.STARTING,
            host=host,
            port=port,
        )
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        app = create_router_app(server_info_fn=self._server_info_payload)

        config = uvicorn.Config(
            app,
            host=self.host,
            port=self.port,
            log_level="warning",
            access_log=False,
        )
        self._server = uvicorn.Server(config)

        self.server_info.status = ServerStatus.AVAILABLE
        self.server_info.last_heartbeat = utc_now()

        self._thread = threading.Thread(
            target=self._server.run,
            name="sarapp-cloud-router",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self.server_info.status = ServerStatus.STOPPING
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def _server_info_payload(self) -> dict[str, Any]:
        self.server_info.last_heartbeat = utc_now()
        return self.server_info.to_dict()

    def health_payload(self) -> dict[str, Any]:
        return {
            "ok": self.server_info.status == ServerStatus.AVAILABLE,
            "server": self._server_info_payload(),
        }
