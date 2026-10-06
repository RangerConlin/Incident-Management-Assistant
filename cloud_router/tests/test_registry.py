import asyncio
import json
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import pytest

from router import config
from router.registry import (
    TunnelBackpressureError,
    TunnelConnection,
    TunnelRegistry,
    TunnelUnavailableError,
)


class _FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_text(self, text: str) -> None:
        self.sent.append(text)


def test_send_request_and_resolve_response() -> None:
    async def _run() -> None:
        conn = TunnelConnection(connect_code="X", server_id="s", server_name="n", websocket=_FakeWebSocket())
        future = await conn.send_request(
            request_id="r1", method="GET", path="/x", query="", headers={}, body_b64=""
        )
        assert json.loads(conn.websocket.sent[0])["type"] == "request"
        conn.resolve_response({"request_id": "r1", "status": 200, "headers": {}, "body": ""})
        result = await asyncio.wait_for(future, timeout=1)
        assert result["status"] == 200

    asyncio.run(_run())


def test_fail_all_rejects_pending_requests() -> None:
    async def _run() -> None:
        conn = TunnelConnection(connect_code="X", server_id="s", server_name="n", websocket=_FakeWebSocket())
        future = await conn.send_request(
            request_id="r1", method="GET", path="/x", query="", headers={}, body_b64=""
        )
        conn.fail_all()
        with pytest.raises(TunnelUnavailableError):
            await future

    asyncio.run(_run())


def test_ws_channel_message_and_close_lifecycle() -> None:
    conn = TunnelConnection(connect_code="X", server_id="s", server_name="n", websocket=_FakeWebSocket())
    queue = conn.register_ws_channel("c1")
    conn.dispatch_ws_message({"channel_id": "c1", "data": "hi", "binary": False})
    assert queue.get_nowait() == {"type": "message", "data": "hi", "binary": False}
    conn.dispatch_ws_close({"channel_id": "c1"})
    assert "c1" not in conn.ws_channels


def test_dispatch_ws_close_carries_remote_closed_reason() -> None:
    conn = TunnelConnection(connect_code="X", server_id="s", server_name="n", websocket=_FakeWebSocket())
    queue = conn.register_ws_channel("c1")
    conn.dispatch_ws_close({"channel_id": "c1"})
    item = queue.get_nowait()
    assert item == {"type": "closed", "reason": "remote_closed", "code": 1000}


def test_fail_all_carries_tunnel_disconnected_reason() -> None:
    conn = TunnelConnection(connect_code="X", server_id="s", server_name="n", websocket=_FakeWebSocket())
    queue = conn.register_ws_channel("c1")
    conn.fail_all()
    item = queue.get_nowait()
    assert item == {"type": "closed", "reason": "tunnel_disconnected", "code": 1001}


def test_send_request_raises_backpressure_at_cap(monkeypatch) -> None:
    monkeypatch.setattr(config, "MAX_PENDING_REQUESTS_PER_TUNNEL", 1)

    async def _run() -> None:
        conn = TunnelConnection(connect_code="X", server_id="s", server_name="n", websocket=_FakeWebSocket())
        await conn.send_request(request_id="r1", method="GET", path="/x", query="", headers={}, body_b64="")
        with pytest.raises(TunnelBackpressureError):
            await conn.send_request(request_id="r2", method="GET", path="/x", query="", headers={}, body_b64="")

    asyncio.run(_run())


def test_register_ws_channel_raises_backpressure_at_cap(monkeypatch) -> None:
    monkeypatch.setattr(config, "MAX_WS_CHANNELS_PER_TUNNEL", 1)

    conn = TunnelConnection(connect_code="X", server_id="s", server_name="n", websocket=_FakeWebSocket())
    conn.register_ws_channel("c1")
    with pytest.raises(TunnelBackpressureError):
        conn.register_ws_channel("c2")


def test_record_pong_updates_last_pong_at() -> None:
    conn = TunnelConnection(connect_code="X", server_id="s", server_name="n", websocket=_FakeWebSocket())
    original = conn.last_pong_at
    conn.record_pong({"type": "pong", "ts": 1.0})
    assert conn.last_pong_at >= original


def test_registry_register_get_deregister() -> None:
    registry = TunnelRegistry()
    conn = TunnelConnection(connect_code="X", server_id="s", server_name="n", websocket=_FakeWebSocket())
    registry.register(conn)
    assert registry.get("X") is conn
    assert registry.active_tunnel_count() == 1
    assert registry.list_connections() == [conn]
    registry.deregister("X")
    assert registry.get("X") is None
    assert registry.active_tunnel_count() == 0
