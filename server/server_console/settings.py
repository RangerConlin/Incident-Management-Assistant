"""Settings helpers for the SARApp Server Console."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from core.networking.server_info import DEFAULT_DISCOVERY_PORT, DEFAULT_SERVER_PORT


def _default_config_path() -> Path:
    """Return a writable settings path for source and PyInstaller launches."""

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "settings" / "server_console.json"
    return Path(__file__).resolve().parents[2] / "settings" / "server_console.json"


DEFAULT_CONFIG_PATH = _default_config_path()


@dataclass(slots=True)
class ServerConsoleSettings:
    """Persistent settings used when the console starts the server process."""

    server_name: str = "SARApp Incident Server"
    host: str = "0.0.0.0"
    port: int = DEFAULT_SERVER_PORT
    discovery_enabled: bool = True
    discovery_port: int = DEFAULT_DISCOVERY_PORT

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
        )
        settings.validate()
        return settings


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
