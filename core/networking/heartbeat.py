"""Heartbeat tracking for discovered and connected SARApp Servers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .server_info import ConnectionHealth, DEFAULT_HEARTBEAT_TIMEOUT_SECONDS, ServerInfo, utc_now


@dataclass(slots=True)
class HeartbeatRecord:
    """Client-side heartbeat data retained for future failover decisions."""

    server: ServerInfo
    first_seen: datetime
    last_heartbeat: datetime
    last_synchronization_timestamp: datetime | None = None

    def health(self, *, now: datetime | None = None, timeout_seconds: float = DEFAULT_HEARTBEAT_TIMEOUT_SECONDS) -> ConnectionHealth:
        now = now or utc_now()
        if self.last_heartbeat.tzinfo is None:
            last = self.last_heartbeat.replace(tzinfo=timezone.utc)
        else:
            last = self.last_heartbeat.astimezone(timezone.utc)
        age = (now.astimezone(timezone.utc) - last).total_seconds()
        return ConnectionHealth.HEALTHY if age <= timeout_seconds else ConnectionHealth.STALE


class HeartbeatTracker:
    """Maintains latest heartbeat metadata for each known server."""

    def __init__(self, *, timeout_seconds: float = DEFAULT_HEARTBEAT_TIMEOUT_SECONDS) -> None:
        self.timeout_seconds = timeout_seconds
        self._records: dict[str, HeartbeatRecord] = {}

    def observe(self, server: ServerInfo, *, observed_at: datetime | None = None) -> HeartbeatRecord:
        observed_at = observed_at or utc_now()
        server.last_heartbeat = observed_at
        record = self._records.get(server.server_id)
        if record is None:
            record = HeartbeatRecord(server=server, first_seen=observed_at, last_heartbeat=observed_at)
            self._records[server.server_id] = record
        else:
            record.server = server
            record.last_heartbeat = observed_at
            record.last_synchronization_timestamp = server.last_synchronization_timestamp
        return record

    def record_for(self, server_id: str) -> HeartbeatRecord | None:
        return self._records.get(server_id)

    def health_for(self, server_id: str) -> ConnectionHealth:
        record = self.record_for(server_id)
        if record is None:
            return ConnectionHealth.UNKNOWN
        return record.health(timeout_seconds=self.timeout_seconds)

    def known_servers(self) -> list[ServerInfo]:
        return [record.server for record in self._records.values()]
