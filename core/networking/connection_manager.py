"""Centralized client connection state for SARApp startup and UI code."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import os
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from .server_info import DEFAULT_SERVER_PORT, HEALTH_PATH, build_base_url, is_sarapp_health_payload


class ConnectionState(str, Enum):
    """High-level connection modes exposed to the rest of the desktop app."""

    LAN = "lan"
    CLOUD = "cloud"
    OFFLINE = "offline"
    DISCONNECTED = "disconnected"


@dataclass(frozen=True)
class ConnectionSnapshot:
    """Immutable view of the current connection state."""

    state: ConnectionState = ConnectionState.DISCONNECTED
    host: Optional[str] = None
    port: Optional[int] = None
    base_url: Optional[str] = None
    server_name: Optional[str] = None
    message: str = "Disconnected"

    @property
    def is_connected(self) -> bool:
        return self.state in {ConnectionState.LAN, ConnectionState.CLOUD}

    @property
    def is_offline(self) -> bool:
        return self.state == ConnectionState.OFFLINE


class ConnectionManager:
    """Owns connection checks so UI code does not duplicate state logic."""

    def __init__(self, timeout_seconds: float = 1.5):
        self.timeout_seconds = timeout_seconds
        self._snapshot = ConnectionSnapshot()

    @property
    def snapshot(self) -> ConnectionSnapshot:
        return self._snapshot

    def check_health(self, host: str, port: int = DEFAULT_SERVER_PORT) -> Optional[dict]:
        """Return a compatible SARApp /health payload, or None when unavailable."""
        base_url = build_base_url(host, port)
        try:
            with urlopen(f"{base_url}{HEALTH_PATH}", timeout=self.timeout_seconds) as response:
                if response.status != 200:
                    return None
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError):
            return None
        if not is_sarapp_health_payload(payload):
            return None
        return payload

    def connect_manual(self, host: str, port: int = DEFAULT_SERVER_PORT) -> bool:
        """Connect to a user-supplied LAN/local server after a health check."""
        payload = self.check_health(host, port)
        if not payload:
            self._snapshot = ConnectionSnapshot(
                state=ConnectionState.DISCONNECTED,
                host=host,
                port=port,
                base_url=build_base_url(host, port),
                message="Manual server health check failed",
            )
            return False
        self._snapshot = ConnectionSnapshot(
            state=ConnectionState.LAN,
            host=host,
            port=port,
            base_url=build_base_url(host, port),
            server_name=str(payload.get("name") or "SARApp Server"),
            message="Connected to LAN/local SARApp server",
        )
        return True

    def connect_cloud(self) -> bool:
        """Try an optional configured cloud URL from SARAPP_CLOUD_URL."""
        cloud_url = str(os.getenv("SARAPP_CLOUD_URL", "")).strip().rstrip("/")
        if not cloud_url:
            return False
        try:
            with urlopen(f"{cloud_url}{HEALTH_PATH}", timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError):
            return False
        if not is_sarapp_health_payload(payload):
            return False
        self._snapshot = ConnectionSnapshot(
            state=ConnectionState.CLOUD,
            base_url=cloud_url,
            server_name=str(payload.get("name") or "SARApp Cloud Server"),
            message="Connected to cloud SARApp server",
        )
        return True

    def discover_lan(self) -> bool:
        """Placeholder LAN discovery hook; existing discovery can be wired here later."""
        # Keep discovery centralized. This first version only performs an inexpensive
        # localhost probe so startup does not block on fixed external network state.
        return self.connect_manual("127.0.0.1", DEFAULT_SERVER_PORT)

    def connect_startup(self) -> bool:
        """Run the startup connection order: LAN/local discovery, then cloud."""
        if self.discover_lan():
            return True
        return self.connect_cloud()

    def work_offline(self) -> None:
        """Switch to the existing desktop-first offline behavior."""
        self._snapshot = ConnectionSnapshot(
            state=ConnectionState.OFFLINE,
            message="Working offline with local SQLite data",
        )
