"""LAN discovery primitives for SARApp.

SARApp uses UDP broadcast for phase-1 discovery because it works without cloud
services, DNS, or preconfigured IP addresses on typical incident LANs.  Manual
connection remains available through :meth:`DiscoveryClient.manual_server` for
networks that block broadcast traffic.
"""

from __future__ import annotations

import json
import logging
import socket
import threading
from collections.abc import Callable
from dataclasses import replace

from .server_info import (
    DEFAULT_DISCOVERY_INTERVAL_SECONDS,
    DEFAULT_DISCOVERY_PORT,
    DiscoveryAnnouncement,
    ServerInfo,
    utc_now,
)

logger = logging.getLogger(__name__)


class DiscoveryBroadcaster:
    """Periodically advertises a SARApp Server on the local broadcast domain."""

    def __init__(
        self,
        server_info: ServerInfo,
        *,
        port: int = DEFAULT_DISCOVERY_PORT,
        interval_seconds: float = DEFAULT_DISCOVERY_INTERVAL_SECONDS,
        broadcast_address: str = "255.255.255.255",
    ) -> None:
        self.server_info = server_info
        self.port = port
        self.interval_seconds = interval_seconds
        self.broadcast_address = broadcast_address
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="sarapp-discovery", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=self.interval_seconds + 1.0)

    def _run(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            while not self._stop_event.is_set():
                try:
                    self.broadcast_once(sock)
                except OSError as exc:
                    logger.warning("Failed to broadcast SARApp discovery packet: %s", exc)
                self._stop_event.wait(self.interval_seconds)

    def broadcast_once(self, sock: socket.socket | None = None) -> None:
        """Send one discovery heartbeat; useful for tests and immediate startup."""

        close_sock = sock is None
        if sock is None:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            current = replace(self.server_info, last_heartbeat=utc_now())
            payload = json.dumps(DiscoveryAnnouncement(current).to_dict()).encode("utf-8")
            sock.sendto(payload, (self.broadcast_address, self.port))
        finally:
            if close_sock:
                sock.close()


class DiscoveryClient:
    """Listens for SARApp Server UDP announcements and normalizes results."""

    def __init__(self, *, port: int = DEFAULT_DISCOVERY_PORT, bind_host: str = "") -> None:
        self.port = port
        self.bind_host = bind_host

    def discover(self, *, timeout_seconds: float = 3.0) -> list[ServerInfo]:
        """Return unique servers heard during the timeout window."""

        servers: dict[str, ServerInfo] = {}
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.bind_host, self.port))
            sock.settimeout(timeout_seconds)
            while True:
                try:
                    data, address = sock.recvfrom(8192)
                except socket.timeout:
                    break
                server = self._decode_packet(data, address[0])
                if server is not None:
                    servers[server.server_id] = server
        return list(servers.values())

    @staticmethod
    def _decode_packet(data: bytes, packet_host: str) -> ServerInfo | None:
        try:
            payload = json.loads(data.decode("utf-8"))
            announcement = DiscoveryAnnouncement.from_dict(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None
        # The advertised host may be 0.0.0.0 because the server binds all
        # interfaces.  Clients must connect to the source address they heard.
        if announcement.server.host in {"", "0.0.0.0", "::"}:
            announcement.server.host = packet_host
        announcement.server.last_heartbeat = utc_now()
        return announcement.server

    @staticmethod
    def manual_server(host: str, port: int, *, name: str = "Manual SARApp Server") -> ServerInfo:
        """Create a server record for manual IP/hostname fallback workflows."""

        server_id = f"manual-{host}-{port}"
        return ServerInfo(server_id=server_id, server_name=name, host=host, port=port)
