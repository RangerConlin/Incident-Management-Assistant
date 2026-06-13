"""SARApp cloud server runtime.

Runs as a headless service.  Discovery is off by default for cloud deployments
but can be enabled for hybrid LAN/cloud setups.
"""

from __future__ import annotations

import socket
import threading
import uuid
from typing import Any

import uvicorn

from networking.discovery import DiscoveryBroadcaster
from networking.server_info import (
    DEFAULT_DISCOVERY_PORT,
    DEFAULT_SERVER_PORT,
    SARAPP_VERSION,
    ServerInfo,
    ServerStatus,
    utc_now,
)
from sarapp_db.api.app import create_app


def _default_server_id() -> str:
    return f"sarapp-cloud-{socket.gethostname()}-{uuid.uuid4().hex[:8]}"


class SARAppServerManager:
    """Owns the SARApp API server and optional LAN discovery broadcaster."""

    def __init__(
        self,
        *,
        host: str = "0.0.0.0",
        port: int = DEFAULT_SERVER_PORT,
        server_id: str | None = None,
        server_name: str | None = None,
        version: str = SARAPP_VERSION,
        discovery_enabled: bool = False,
        discovery_port: int = DEFAULT_DISCOVERY_PORT,
    ) -> None:
        self.host = host
        self.port = port
        self.discovery_enabled = discovery_enabled
        self.server_info = ServerInfo(
            server_id=server_id or _default_server_id(),
            server_name=server_name or f"SARApp Cloud Server on {socket.gethostname()}",
            version=version,
            status=ServerStatus.STARTING,
            host=host,
            port=port,
        )
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self._broadcaster = DiscoveryBroadcaster(self.server_info, port=discovery_port)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        app = create_app(server_info_fn=self._server_info_payload)

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
            name="sarapp-cloud-server",
            daemon=True,
        )
        self._thread.start()

        if self.discovery_enabled:
            self._broadcaster.server_info = self.server_info
            self._broadcaster.start()

    def stop(self) -> None:
        self.server_info.status = ServerStatus.STOPPING
        self._broadcaster.stop()
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
