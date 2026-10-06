"""Shared connectivity data structures for SARApp clients and servers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

SARAPP_VERSION = "0.1-connectivity"
DEFAULT_DISCOVERY_PORT = 45454
DEFAULT_SERVER_PORT = 8765
DEFAULT_DISCOVERY_INTERVAL_SECONDS = 2.0
DEFAULT_HEARTBEAT_TIMEOUT_SECONDS = 10.0
DISCOVERY_MESSAGE_TYPE = "sarapp.server.heartbeat"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def datetime_to_wire(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def datetime_from_wire(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class ServerStatus(str, Enum):
    STARTING = "starting"
    AVAILABLE = "available"
    DEGRADED = "degraded"
    STOPPING = "stopping"


class ConnectionMode(str, Enum):
    LAN = "lan"
    CLOUD = "cloud"
    OFFLINE = "offline"


class ConnectionState(str, Enum):
    DISCONNECTED = "disconnected"
    DISCOVERING = "discovering"
    CONNECTING = "connecting"
    CONNECTED_LAN = "connected_lan"
    CONNECTED_CLOUD = "connected_cloud"
    OFFLINE = "offline"


class ConnectionHealth(str, Enum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    STALE = "stale"
    DISCONNECTED = "disconnected"


@dataclass(slots=True)
class ServerInfo:
    """Network identity and failover metadata for a SARApp Server."""

    server_id: str
    server_name: str
    version: str = SARAPP_VERSION
    status: ServerStatus = ServerStatus.AVAILABLE
    host: str = "127.0.0.1"
    port: int = DEFAULT_SERVER_PORT
    connected_timestamp: datetime | None = None
    last_heartbeat: datetime | None = None
    last_synchronization_timestamp: datetime | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["connected_timestamp"] = datetime_to_wire(self.connected_timestamp)
        payload["last_heartbeat"] = datetime_to_wire(self.last_heartbeat)
        payload["last_synchronization_timestamp"] = datetime_to_wire(self.last_synchronization_timestamp)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ServerInfo":
        return cls(
            server_id=str(payload["server_id"]),
            server_name=str(payload.get("server_name") or payload["server_id"]),
            version=str(payload.get("version") or SARAPP_VERSION),
            status=ServerStatus(str(payload.get("status") or ServerStatus.AVAILABLE.value)),
            host=str(payload.get("host") or "127.0.0.1"),
            port=int(payload.get("port") or DEFAULT_SERVER_PORT),
            connected_timestamp=datetime_from_wire(payload.get("connected_timestamp")),
            last_heartbeat=datetime_from_wire(payload.get("last_heartbeat")),
            last_synchronization_timestamp=datetime_from_wire(payload.get("last_synchronization_timestamp")),
        )


@dataclass(slots=True)
class DiscoveryAnnouncement:
    server: ServerInfo
    message_type: str = DISCOVERY_MESSAGE_TYPE

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.message_type, "server": self.server.to_dict()}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DiscoveryAnnouncement":
        if payload.get("type") != DISCOVERY_MESSAGE_TYPE:
            raise ValueError("Not a SARApp discovery announcement")
        return cls(server=ServerInfo.from_dict(dict(payload["server"])))


@dataclass(slots=True)
class ConnectionSnapshot:
    state: ConnectionState
    mode: ConnectionMode | None
    health: ConnectionHealth
    server: ServerInfo | None = None
    message: str = ""

    @property
    def is_connected(self) -> bool:
        return self.state in {ConnectionState.CONNECTED_LAN, ConnectionState.CONNECTED_CLOUD}
