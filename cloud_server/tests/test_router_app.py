"""Integration tests for the cloud router's FastAPI app.

These drive the ASGI app directly with a minimal in-process harness (a
single asyncio event loop, no background threads) rather than Starlette's
``TestClient``, because these tests need two concurrently-open connections
(a fake LAN-server tunnel and a field-device request/socket) blocked on each
other at the same time — mixing that with ``TestClient``'s thread-based
portal deadlocks.
"""

import asyncio
import base64
import json
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import httpx
import pytest
from fastapi.testclient import TestClient

from router.app import create_router_app


class ASGIWebSocketSession:
    """Minimal in-process ASGI WebSocket driver for a single event loop."""

    def __init__(self, app, path: str) -> None:
        self.app = app
        self.path = path
        self._to_app: asyncio.Queue = asyncio.Queue()
        self._from_app: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task | None = None

    async def connect(self) -> None:
        scope = {
            "type": "websocket",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "path": self.path,
            "raw_path": self.path.encode("utf-8"),
            "root_path": "",
            "scheme": "ws",
            "headers": [],
            "query_string": b"",
            "client": ("testclient", 123),
            "server": ("testserver", 80),
        }

        async def receive():
            return await self._to_app.get()

        async def send(message):
            await self._from_app.put(message)

        self._task = asyncio.create_task(self.app(scope, receive, send))
        await self._to_app.put({"type": "websocket.connect"})
        message = await self._from_app.get()
        assert message["type"] == "websocket.accept"

    async def send_text(self, text: str) -> None:
        await self._to_app.put({"type": "websocket.receive", "text": text})

    async def receive_text(self) -> str:
        message = await self._from_app.get()
        assert message["type"] == "websocket.send"
        return message["text"]

    async def close(self) -> None:
        await self._to_app.put({"type": "websocket.disconnect", "code": 1000})
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=2)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass


async def _open_registered_tunnel(app, connect_code: str) -> ASGIWebSocketSession:
    tunnel = ASGIWebSocketSession(app, "/tunnel/register")
    await tunnel.connect()
    await tunnel.send_text(
        json.dumps(
            {
                "type": "register",
                "connect_code": connect_code,
                "server_id": "srv-1",
                "server_name": "Test LAN Server",
                "token": "",
            }
        )
    )
    ack = json.loads(await tunnel.receive_text())
    assert ack["type"] == "registered"
    return tunnel


def test_http_proxy_round_trip() -> None:
    async def _run() -> None:
        app = create_router_app()
        tunnel = await _open_registered_tunnel(app, "TEST-0001")

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            request_task = asyncio.create_task(client.get("/r/TEST-0001/api/health-check"))

            request_frame = json.loads(await tunnel.receive_text())
            assert request_frame["type"] == "request"
            assert request_frame["method"] == "GET"
            assert request_frame["path"] == "/api/health-check"

            await tunnel.send_text(
                json.dumps(
                    {
                        "type": "response",
                        "request_id": request_frame["request_id"],
                        "status": 200,
                        "headers": {"content-type": "application/json"},
                        "body": base64.b64encode(b'{"ok": true}').decode("ascii"),
                    }
                )
            )

            response = await request_task
            assert response.status_code == 200
            assert response.json() == {"ok": True}

        await tunnel.close()

    asyncio.run(_run())


def test_http_proxy_returns_503_when_lan_server_offline() -> None:
    app = create_router_app()
    client = TestClient(app)

    response = client.get("/r/NOBODY-HOME/api/health-check")
    assert response.status_code == 503


def test_ws_proxy_round_trip() -> None:
    async def _run() -> None:
        app = create_router_app()
        tunnel = await _open_registered_tunnel(app, "TEST-0002")

        field_ws = ASGIWebSocketSession(app, "/r/TEST-0002/api/incidents/TEST-1/ws")
        await field_ws.connect()

        open_frame = json.loads(await tunnel.receive_text())
        assert open_frame["type"] == "ws_open"
        assert open_frame["path"] == "/api/incidents/TEST-1/ws"
        channel_id = open_frame["channel_id"]

        await tunnel.send_text(
            json.dumps(
                {
                    "type": "ws_message",
                    "channel_id": channel_id,
                    "binary": False,
                    "data": json.dumps({"collection": "personnel", "op": "updated"}),
                }
            )
        )

        message = await field_ws.receive_text()
        assert json.loads(message) == {"collection": "personnel", "op": "updated"}

        await field_ws.send_text("ack")
        echoed_frame = json.loads(await tunnel.receive_text())
        assert echoed_frame["type"] == "ws_message"
        assert echoed_frame["channel_id"] == channel_id
        assert echoed_frame["data"] == "ack"

        await field_ws.close()

        close_frame = json.loads(await tunnel.receive_text())
        assert close_frame["type"] == "ws_close"
        assert close_frame["channel_id"] == channel_id

        await tunnel.close()

    asyncio.run(_run())


def test_tunnel_registration_rejected_with_bad_token(monkeypatch) -> None:
    monkeypatch.setenv("SARAPP_CLOUD_ROUTER_TOKEN", "expected-secret")

    async def _run() -> None:
        app = create_router_app()
        tunnel = ASGIWebSocketSession(app, "/tunnel/register")
        await tunnel.connect()
        await tunnel.send_text(
            json.dumps(
                {
                    "type": "register",
                    "connect_code": "TEST-0003",
                    "server_id": "srv-1",
                    "server_name": "Test LAN Server",
                    "token": "wrong-secret",
                }
            )
        )
        message = await tunnel._from_app.get()
        assert message["type"] == "websocket.close"

    asyncio.run(_run())
