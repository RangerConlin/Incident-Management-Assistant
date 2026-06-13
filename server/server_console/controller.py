"""Testable server-control logic for the SARApp Server Console."""

from __future__ import annotations

import json
import socket
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import Enum
from typing import Any

from server.server_manager import SARAppServerManager

from .settings import ServerConsoleSettings


class ConsoleServerState(str, Enum):
    """Runtime state labels displayed by the console window."""

    STOPPED = "Stopped"
    STARTING = "Starting"
    RUNNING = "Running"
    STOPPING = "Stopping"
    ERROR = "Error"
    MONITORING = "Monitoring"


@dataclass(slots=True)
class PortCheckResult:
    """Result of checking a configured host/port before server startup."""

    available: bool
    sarapp_server: bool = False
    message: str = ""
    payload: dict[str, Any] | None = None


@dataclass(slots=True)
class HealthCheckResult:
    """Normalized health-check response for UI and tests."""

    status: str
    ok: bool = False
    payload: dict[str, Any] | None = None
    message: str = ""


def fetch_health(base_url: str, *, timeout_seconds: float = 1.0) -> HealthCheckResult:
    """Call /health with a timeout so monitoring never blocks indefinitely."""

    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/health", timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return HealthCheckResult(status="Error", message=str(exc))
    is_sarapp = isinstance(payload, dict) and isinstance(payload.get("server"), dict)
    return HealthCheckResult(status="Healthy" if payload.get("ok") and is_sarapp else "Error", ok=bool(payload.get("ok") and is_sarapp), payload=payload)


def check_port(settings: ServerConsoleSettings, *, timeout_seconds: float = 0.75) -> PortCheckResult:
    """Identify whether the configured port is free, SARApp, or another service."""

    health = fetch_health(settings.base_url, timeout_seconds=timeout_seconds)
    if health.ok:
        return PortCheckResult(False, True, "A SARApp server is already running on this port.", health.payload)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout_seconds)
        if sock.connect_ex((settings.health_host, settings.port)) == 0:
            return PortCheckResult(False, False, "The configured port is already in use by another service.")
    return PortCheckResult(True, False, "Port is available.")


class ServerConsoleController:
    """Owns the in-process server manager while keeping long work off the UI thread."""

    def __init__(self, settings: ServerConsoleSettings) -> None:
        self.settings = settings
        self.state = ConsoleServerState.STOPPED
        self.manager: SARAppServerManager | None = None
        self.last_error = ""
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the existing SARApp server engine with console settings."""

        with self._lock:
            self.settings.validate()
            conflict = check_port(self.settings)
            if not conflict.available:
                self.state = ConsoleServerState.ERROR
                self.last_error = conflict.message
                raise RuntimeError(conflict.message)
            self.state = ConsoleServerState.STARTING
            self.manager = SARAppServerManager(
                host=self.settings.host,
                port=self.settings.port,
                server_name=self.settings.server_name,
                discovery_enabled=self.settings.discovery_enabled,
                discovery_port=self.settings.discovery_port,
            )
            try:
                self.manager.start()
            except OSError as exc:
                self.state = ConsoleServerState.ERROR
                self.last_error = str(exc)
                raise
            self.state = ConsoleServerState.RUNNING
            self.last_error = ""

    def stop(self) -> None:
        """Stop the managed server cleanly without assuming it exists."""

        with self._lock:
            if self.manager is None:
                self.state = ConsoleServerState.STOPPED
                return
            self.state = ConsoleServerState.STOPPING
            self.manager.stop()
            self.manager = None
            self.state = ConsoleServerState.STOPPED

    def restart(self, settings: ServerConsoleSettings | None = None) -> None:
        """Apply optional settings and restart the server engine."""

        self.stop()
        if settings is not None:
            self.settings = settings
        self.start()

    def monitor_existing(self) -> None:
        """Mark this console as monitoring an already-running compatible server."""

        self.manager = None
        self.state = ConsoleServerState.MONITORING
