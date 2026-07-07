import asyncio
import json
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import pytest

from router.registry import TunnelConnection, TunnelRegistry, TunnelUnavailableError


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


def test_registry_register_get_deregister() -> None:
    registry = TunnelRegistry()
    conn = TunnelConnection(connect_code="X", server_id="s", server_name="n", websocket=_FakeWebSocket())
    registry.register(conn)
    assert registry.get("X") is conn
    registry.deregister("X")
    assert registry.get("X") is None
