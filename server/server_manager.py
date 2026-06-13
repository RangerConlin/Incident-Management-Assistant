"""Minimal SARApp Server runtime for connectivity phase 1.

This module deliberately uses the Python standard library rather than adding a
new web framework dependency.  It exposes only health/server-info endpoints and
LAN discovery heartbeats; data APIs and database integration remain out of scope
for this branch.
"""

from __future__ import annotations

import argparse
import json
import socket
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from core.networking.discovery import DiscoveryBroadcaster
from core.networking.server_info import (
    DEFAULT_DISCOVERY_PORT,
    DEFAULT_SERVER_PORT,
    SARAPP_VERSION,
    ServerInfo,
    ServerStatus,
    utc_now,
)


def _default_server_id() -> str:
    """Generate a stable-looking process ID without touching persistent storage."""

    return f"sarapp-{socket.gethostname()}-{uuid.uuid4().hex[:8]}"


class SARAppServerManager:
    """Owns the phase-1 health server and LAN discovery broadcaster."""

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
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._broadcaster = DiscoveryBroadcaster(self.server_info, port=discovery_port)

    def start(self) -> None:
        """Start HTTP health endpoints and LAN heartbeat advertisements."""

        if self._thread and self._thread.is_alive():
            return
        manager = self

        class Handler(_SARAppHealthHandler):
            server_manager = manager

        self._httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        # Preserve the actual port if caller passed 0 for tests/dynamic binding.
        self.port = int(self._httpd.server_address[1])
        self.server_info.port = self.port
        self.server_info.status = ServerStatus.AVAILABLE
        self.server_info.last_heartbeat = utc_now()
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="sarapp-server", daemon=True)
        self._thread.start()
        # Discovery is optional for the Server Console settings, but remains
        # enabled by default so the existing command-line entry point continues
        # to advertise exactly as before.
        if self.discovery_enabled:
            self._broadcaster.server_info = self.server_info
            self._broadcaster.start()

    def stop(self) -> None:
        """Stop discovery first, then the health server."""

        self.server_info.status = ServerStatus.STOPPING
        # Stop UDP discovery before HTTP shutdown so clients stop seeing this
        # server as soon as the process begins leaving service.
        self._broadcaster.stop()
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def health_payload(self) -> dict[str, Any]:
        """Payload returned by /health for clients and smoke checks."""

        self.server_info.last_heartbeat = utc_now()
        return {
            "ok": self.server_info.status == ServerStatus.AVAILABLE,
            "server": self.server_info.to_dict(),
        }


class _SARAppHealthHandler(BaseHTTPRequestHandler):
    """Small JSON handler for phase-1 connectivity checks."""

    server_manager: SARAppServerManager

    def do_GET(self) -> None:  # noqa: N802 - stdlib callback name
        if self.path.rstrip("/") == "/health":
            self._write_json(self.server_manager.health_payload())
            return
        if self.path.rstrip("/") == "/server-info":
            self._write_json(self.server_manager.server_info.to_dict())
            return
        self.send_error(404, "Not found")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - stdlib signature
        # Keep the desktop app console quiet; production logging can be added
        # around the manager without coupling tests to http.server output.
        return

    def _write_json(self, payload: dict[str, Any], *, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start a phase-1 SARApp connectivity server")
    parser.add_argument("--host", default="0.0.0.0", help="Host/interface to bind")
    parser.add_argument("--port", type=int, default=DEFAULT_SERVER_PORT, help="HTTP health port")
    parser.add_argument("--name", default=None, help="Advertised server name")
    args = parser.parse_args(argv)

    manager = SARAppServerManager(host=args.host, port=args.port, server_name=args.name)
    manager.start()
    print(f"SARApp Server advertising as {manager.server_info.server_name} on port {manager.port}")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        manager.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
