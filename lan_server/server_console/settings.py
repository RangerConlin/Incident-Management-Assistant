"""Settings helpers for the SARApp Server Console."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from lan_server.networking.server_info import DEFAULT_DISCOVERY_PORT, DEFAULT_SERVER_PORT


def _default_config_path() -> Path:
    """Return a writable settings path for source and PyInstaller launches."""

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "settings" / "server_console.json"
    # In source mode __file__ is lan_server/server_console/settings.py,
    # so parents[1] is lan_server/ — settings are kept inside the server folder.
    return Path(__file__).resolve().parents[1] / "settings" / "server_console.json"


DEFAULT_CONFIG_PATH = _default_config_path()


@dataclass(slots=True)
class ServerConsoleSettings:
    """Persistent settings used when the console starts the server process."""

    server_name: str = "SARApp Incident Server"
    host: str = "0.0.0.0"
    port: int = DEFAULT_SERVER_PORT
    discovery_enabled: bool = True
    discovery_port: int = DEFAULT_DISCOVERY_PORT
    # Cloud reverse-tunnel options.  Empty URL keeps tunneling disabled; an
    # empty connect code lets the tunnel client auto-generate one.  The tunnel
    # registration token stays env-only (SARAPP_CLOUD_ROUTER_TOKEN) and is
    # deliberately never persisted here.
    cloud_router_url: str = ""
    connect_code: str = ""
    # Path to an end user's uploaded Firebase Admin SDK credentials file.
    # Empty means "use the bundled default key" (see lan_server/firebase_credentials.py) —
    # uploading is a one-time action, not required on every start.
    firebase_credentials_path: str = ""

    @property
    def health_host(self) -> str:
        """Return a loopback-safe host for local health checks and browser URLs."""

        return "127.0.0.1" if self.host in {"", "0.0.0.0", "::"} else self.host

    @property
    def base_url(self) -> str:
        """Return the HTTP address copied by the console and used for checks."""

        return f"http://{self.health_host}:{self.port}"

    def validate(self) -> None:
        """Validate settings before saving or starting networking components."""

        validate_port(self.port, field_name="port")
        validate_port(self.discovery_port, field_name="discovery_port")
        if not self.server_name.strip():
            raise ValueError("Server name is required.")
        if not self.host.strip():
            raise ValueError("Host is required.")
        validate_cloud_router_url(self.cloud_router_url)
        validate_connect_code(self.connect_code)

    def to_dict(self) -> dict[str, Any]:
        """Serialize settings to a JSON-compatible dictionary."""

        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ServerConsoleSettings":
        """Load settings from a dictionary while tolerating older config files."""

        defaults = cls()
        settings = cls(
            server_name=str(payload.get("server_name") or defaults.server_name),
            host=str(payload.get("host") or defaults.host),
            port=int(payload.get("port") or DEFAULT_SERVER_PORT),
            discovery_enabled=bool(payload.get("discovery_enabled", True)),
            discovery_port=int(payload.get("discovery_port") or DEFAULT_DISCOVERY_PORT),
            cloud_router_url=str(payload.get("cloud_router_url") or "").strip(),
            connect_code=str(payload.get("connect_code") or "").strip().upper(),
            firebase_credentials_path=str(payload.get("firebase_credentials_path") or "").strip(),
        )
        settings.validate()
        return settings


_CONNECT_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9-]{2,31}$")


def validate_cloud_router_url(value: str) -> str:
    """Validate the optional cloud router tunnel-registration URL."""

    url = value.strip()
    if url and not url.startswith(("ws://", "wss://")):
        raise ValueError("Cloud router URL must start with ws:// or wss://.")
    return url


def validate_connect_code(value: str) -> str:
    """Validate the optional operator-chosen connect code (e.g. ABCD-1234)."""

    code = value.strip().upper()
    if code and not _CONNECT_CODE_PATTERN.match(code):
        raise ValueError(
            "Connect code must be 3-32 characters using letters, digits, and dashes."
        )
    return code


def validate_port(value: int | str, *, field_name: str = "port") -> int:
    """Validate a TCP/UDP port value and return it as an integer."""

    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer between 1 and 65535.") from exc
    if not 1 <= port <= 65535:
        raise ValueError(f"{field_name} must be between 1 and 65535.")
    return port


class ServerConsoleSettingsStore:
    """JSON-backed settings store that is independent of the process cwd."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DEFAULT_CONFIG_PATH

    def load(self) -> ServerConsoleSettings:
        """Load settings, returning defaults when no console config exists yet."""

        if not self.path.exists():
            return ServerConsoleSettings()
        with self.path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return ServerConsoleSettings.from_dict(dict(payload))

    def save(self, settings: ServerConsoleSettings) -> None:
        """Persist validated settings for future console launches."""

        settings.validate()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(settings.to_dict(), handle, indent=2, sort_keys=True)
            handle.write("\n")
