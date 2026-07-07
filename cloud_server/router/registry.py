"""In-memory registry of LAN servers connected to the cloud router via
reverse tunnel, keyed by connect code.

See ``Design Documents/Instructions/cloud_router_architecture.md`` for the
full tunnel frame protocol these connections speak.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any


class TunnelUnavailableError(Exception):
    """Raised when the tunnel disconnects while a request is in flight."""


@dataclass
class TunnelConnection:
    """One LAN server's persistent reverse-tunnel connection."""

    connect_code: str
    server_id: str
    server_name: str
    websocket: Any
    connected_at: float = field(default_factory=time.monotonic)
    pending_requests: dict[str, "asyncio.Future[dict[str, Any]]"] = field(default_factory=dict)
    ws_channels: dict[str, "asyncio.Queue[dict[str, Any]]"] = field(default_factory=dict)
    _send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def _send(self, frame: dict[str, Any]) -> None:
        async with self._send_lock:
            await self.websocket.send_text(json.dumps(frame))

    async def send_request(
        self,
        *,
        request_id: str,
        method: str,
        path: str,
        query: str,
        headers: dict[str, str],
        body_b64: str,
    ) -> "asyncio.Future[dict[str, Any]]":
        loop = asyncio.get_running_loop()
        future: "asyncio.Future[dict[str, Any]]" = loop.create_future()
        self.pending_requests[request_id] = future
        await self._send(
            {
                "type": "request",
                "request_id": request_id,
                "method": method,
                "path": path,
                "query": query,
                "headers": headers,
                "body": body_b64,
            }
        )
        return future

    def resolve_response(self, frame: dict[str, Any]) -> None:
        request_id = frame.get("request_id")
        future = self.pending_requests.pop(request_id, None)
        if future is not None and not future.done():
            future.set_result(frame)

    def register_ws_channel(self, channel_id: str) -> "asyncio.Queue[dict[str, Any]]":
        queue: "asyncio.Queue[dict[str, Any]]" = asyncio.Queue()
        self.ws_channels[channel_id] = queue
        return queue

    async def open_ws_channel(self, channel_id: str, path: str) -> None:
        await self._send({"type": "ws_open", "channel_id": channel_id, "path": path})

    async def send_ws_message(self, channel_id: str, data: str, *, binary: bool) -> None:
        await self._send({"type": "ws_message", "channel_id": channel_id, "data": data, "binary": binary})

    async def send_ws_close(self, channel_id: str) -> None:
        try:
            await self._send({"type": "ws_close", "channel_id": channel_id})
        except Exception:  # noqa: BLE001 - tunnel may already be gone
            pass

    def dispatch_ws_message(self, frame: dict[str, Any]) -> None:
        queue = self.ws_channels.get(frame.get("channel_id"))
        if queue is not None:
            queue.put_nowait(
                {"type": "message", "data": frame.get("data", ""), "binary": bool(frame.get("binary"))}
            )

    def dispatch_ws_close(self, frame: dict[str, Any]) -> None:
        queue = self.ws_channels.pop(frame.get("channel_id"), None)
        if queue is not None:
            queue.put_nowait({"type": "closed"})

    def close_ws_channel_locally(self, channel_id: str) -> None:
        self.ws_channels.pop(channel_id, None)

    def fail_all(self) -> None:
        """Called once when the tunnel itself drops."""

        for future in self.pending_requests.values():
            if not future.done():
                future.set_exception(TunnelUnavailableError("LAN server tunnel disconnected"))
        self.pending_requests.clear()
        for queue in self.ws_channels.values():
            queue.put_nowait({"type": "closed"})
        self.ws_channels.clear()


class TunnelRegistry:
    """Tracks every currently-connected LAN server by its connect code."""

    def __init__(self) -> None:
        self._connections: dict[str, TunnelConnection] = {}

    def register(self, connection: TunnelConnection) -> None:
        self._connections[connection.connect_code] = connection

    def deregister(self, connect_code: str) -> None:
        self._connections.pop(connect_code, None)

    def get(self, connect_code: str) -> TunnelConnection | None:
        return self._connections.get(connect_code)


registry = TunnelRegistry()
