"""Centralized connectivity orchestration for SARApp clients.

The rest of the application should depend on :class:`ConnectionManager` state
instead of knowing whether a server was found via LAN broadcast, cloud health
checks, manual entry, or offline fallback.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Protocol

import httpx

from .discovery import DiscoveryClient
from .heartbeat import HeartbeatTracker
from .server_info import (
    ConnectionHealth,
    ConnectionMode,
    ConnectionSnapshot,
    ConnectionState,
    ServerInfo,
    utc_now,
)

logger = logging.getLogger(__name__)


class SnapshotListener(Protocol):
    def __call__(self, snapshot: ConnectionSnapshot) -> None: ...


class ConnectionManager:
    """Discovers, connects, monitors, and exposes SARApp connectivity state."""

    def __init__(
        self,
        *,
        discovery_client: DiscoveryClient | None = None,
        cloud_url: str | None = None,
        request_timeout_seconds: float = 2.0,
        heartbeat_timeout_seconds: float = 10.0,
    ) -> None:
        self.discovery_client = discovery_client or DiscoveryClient()
        self.cloud_url = cloud_url
        self.request_timeout_seconds = request_timeout_seconds
        self.heartbeats = HeartbeatTracker(timeout_seconds=heartbeat_timeout_seconds)
        self._snapshot = ConnectionSnapshot(
            state=ConnectionState.DISCONNECTED,
            mode=None,
            health=ConnectionHealth.DISCONNECTED,
            message="Not connected",
        )
        self._listeners: list[SnapshotListener] = []

    @property
    def snapshot(self) -> ConnectionSnapshot:
        return self._snapshot

    def add_listener(self, listener: SnapshotListener) -> None:
        self._listeners.append(listener)

    def startup_connect(
        self, *, discovery_timeout_seconds: float = 3.0
    ) -> ConnectionSnapshot:
        """Run the launch workflow: LAN discovery, cloud fallback, offline prompt state."""

        self._set_snapshot(
            ConnectionState.DISCOVERING,
            None,
            ConnectionHealth.UNKNOWN,
            "Searching LAN for SARApp Servers",
        )
        servers = self.discover_servers(timeout_seconds=discovery_timeout_seconds)
        if servers:
            return self.connect_to_server(servers[0], mode=ConnectionMode.LAN)

        cloud_snapshot = self.try_cloud_connection()
        if cloud_snapshot.is_connected:
            return cloud_snapshot

        # Do not silently switch to offline: the UI decides whether the user
        # accepts Offline Mode, but the manager clearly exposes that it is valid.
        self._set_snapshot(
            ConnectionState.DISCONNECTED,
            None,
            ConnectionHealth.DISCONNECTED,
            "No LAN server found and cloud is unavailable",
        )
        return self.snapshot

    def discover_servers(self, *, timeout_seconds: float = 3.0) -> list[ServerInfo]:
        servers = self.discovery_client.discover(timeout_seconds=timeout_seconds)
        for server in servers:
            self.heartbeats.observe(server)
        return servers

    def connect_to_server(
        self, server: ServerInfo, *, mode: ConnectionMode
    ) -> ConnectionSnapshot:
        self._set_snapshot(
            ConnectionState.CONNECTING,
            mode,
            ConnectionHealth.UNKNOWN,
            f"Connecting to {server.server_name}",
            server,
        )
        if not self._check_server_health(server.base_url):
            self._set_snapshot(
                ConnectionState.DISCONNECTED,
                None,
                ConnectionHealth.DISCONNECTED,
                f"Unable to connect to {server.server_name}",
                server,
            )
            return self.snapshot
        connected = replace(server, connected_timestamp=utc_now(), last_heartbeat=utc_now())
        self.heartbeats.observe(connected)
        state = (
            ConnectionState.CONNECTED_LAN
            if mode == ConnectionMode.LAN
            else ConnectionState.CONNECTED_CLOUD
        )
        self._set_snapshot(
            state,
            mode,
            ConnectionHealth.HEALTHY,
            f"Connected to {connected.server_name}",
            connected,
        )
        return self.snapshot

    def connect_manual(self, host: str, port: int) -> ConnectionSnapshot:
        """Manual connection fallback for broadcast-restricted networks."""

        return self.connect_to_server(DiscoveryClient.manual_server(host, port), mode=ConnectionMode.LAN)

    def try_cloud_connection(self) -> ConnectionSnapshot:
        if not self.cloud_url:
            self._set_snapshot(
                ConnectionState.DISCONNECTED,
                None,
                ConnectionHealth.DISCONNECTED,
                "Cloud URL is not configured",
            )
            return self.snapshot
        from urllib.parse import urlparse
        _parsed = urlparse(self.cloud_url)
        _cloud_port = _parsed.port or (443 if _parsed.scheme == "https" else 80)
        cloud = ServerInfo(
            server_id="cloud",
            server_name="SARApp Cloud",
            host=_parsed.hostname,
            port=_cloud_port,
        )
        if not self._check_server_health(self.cloud_url.rstrip("/")):
            self._set_snapshot(
                ConnectionState.DISCONNECTED,
                None,
                ConnectionHealth.DISCONNECTED,
                "Cloud is unavailable",
            )
            return self.snapshot
        self._set_snapshot(
            ConnectionState.CONNECTED_CLOUD,
            ConnectionMode.CLOUD,
            ConnectionHealth.HEALTHY,
            "Connected to SARApp Cloud",
            cloud,
        )
        return self.snapshot

    def enter_offline_mode(self) -> ConnectionSnapshot:
        self._set_snapshot(ConnectionState.OFFLINE, ConnectionMode.OFFLINE, ConnectionHealth.DISCONNECTED, "Offline Mode active")
        return self.snapshot

    def refresh_health(self) -> ConnectionSnapshot:
        """Update health from heartbeat age; future failover can hook in here."""

        server = self.snapshot.server
        if server is None:
            return self.snapshot
        health = self.heartbeats.health_for(server.server_id)
        if health == ConnectionHealth.STALE:
            self._set_snapshot(self.snapshot.state, self.snapshot.mode, health, "Server heartbeat is stale", server)
        else:
            self._set_snapshot(self.snapshot.state, self.snapshot.mode, health, self.snapshot.message, server)
        return self.snapshot

    def _check_server_health(self, base_url: str) -> bool:
        try:
            response = httpx.get(f"{base_url}/health", timeout=self.request_timeout_seconds)
            return 200 <= response.status_code < 300
        except httpx.HTTPError as exc:
            logger.info("SARApp server health check failed for %s: %s", base_url, exc)
            return False

    def _set_snapshot(
        self,
        state: ConnectionState,
        mode: ConnectionMode | None,
        health: ConnectionHealth,
        message: str,
        server: ServerInfo | None = None,
    ) -> None:
        self._snapshot = ConnectionSnapshot(state=state, mode=mode, health=health, server=server, message=message)
        for listener in list(self._listeners):
            listener(self._snapshot)
