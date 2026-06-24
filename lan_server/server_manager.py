"""SARApp standalone LAN server runtime.

Runs as a separate program from the client.  Exposes the full SARApp API via
uvicorn and advertises itself on the LAN via UDP discovery.
"""

from __future__ import annotations

import argparse
import socket
import threading
import time
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
    return f"sarapp-{socket.gethostname()}-{uuid.uuid4().hex[:8]}"


class SARAppServerManager:
    """Owns the SARApp API server and LAN discovery broadcaster."""

    def __init__(
        self,
        *,
        host: str = "0.0.0.0",
        port: int = DEFAULT_SERVER_PORT,
        server_id: str | None = None,
        server_name: str | None = None,
        version: str = SARAPP_VERSION,
        discovery_enabled: bool = True,
        discovery_port: int = DEFAULT_DISCOVERY_PORT,
    ) -> None:
        self.host = host
        self.port = port
        self.discovery_enabled = discovery_enabled
        self.server_info = ServerInfo(
            server_id=server_id or _default_server_id(),
            server_name=server_name or f"SARApp Server on {socket.gethostname()}",
            version=version,
            status=ServerStatus.STARTING,
            host=host,
            port=port,
        )
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self._broadcaster = DiscoveryBroadcaster(self.server_info, port=discovery_port)

    def start(self) -> None:
        """Start the API server in a background thread and begin LAN discovery."""
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
            name="sarapp-lan-server",
            daemon=True,
        )
        self._thread.start()

        # Wait for uvicorn to actually finish binding before returning, and
        # resolve the real bound port — when port=0 was requested (let the OS
        # pick a free port), the caller-supplied value never reflects what
        # actually got bound.
        deadline = time.monotonic() + 5.0
        while not getattr(self._server, "started", False) and time.monotonic() < deadline:
            time.sleep(0.01)
        try:
            actual_port = self._server.servers[0].sockets[0].getsockname()[1]
            self.port = actual_port
            self.server_info.port = actual_port
        except Exception:
            pass

        if self.discovery_enabled:
            self._broadcaster.server_info = self.server_info
            self._broadcaster.start()

    def stop(self) -> None:
        """Stop discovery then shut down the API server."""
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start the SARApp LAN server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=DEFAULT_SERVER_PORT)
    parser.add_argument("--name", default=None)
    args = parser.parse_args(argv)

    manager = SARAppServerManager(host=args.host, port=args.port, server_name=args.name)
    manager.start()
    print(f"SARApp Server running at http://{args.host}:{manager.port}")
    print(f"API docs: http://localhost:{manager.port}/docs")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        manager.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
