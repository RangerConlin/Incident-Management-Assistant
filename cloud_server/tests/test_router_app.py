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

from router import config
from router.app import create_router_app


class ASGIWebSocketSession:
    """Minimal in-process ASGI WebSocket driver for a single event loop."""

    def __init__(self, app, path: str) -> None:
        self.app = app
        self.path = path
        self._to_app: asyncio.Queue = asyncio.Queue()
        self._from_app: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task | None = None

    async def start(self) -> dict:
        """Start the ASGI app and send the connect event; return the app's
        first reply (``websocket.accept`` on success, ``websocket.close`` if
        the handshake is rejected)."""
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
        return await self._from_app.get()

    async def connect(self) -> None:
        message = await self.start()
        assert message["type"] == "websocket.accept"

    async def send_text(self, text: str) -> None:
        await self._to_app.put({"type": "websocket.receive", "text": text})

    async def receive_text(self) -> str:
        message = await self._from_app.get()
        assert message["type"] == "websocket.send"
        return message["text"]

    async def receive_raw(self) -> dict:
        return await self._from_app.get()

    async def close(self) -> None:
        await self._to_app.put({"type": "websocket.disconnect", "code": 1000})
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=2)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass


async def _open_registered_tunnel(app, connect_code: str, token: str = "") -> ASGIWebSocketSession:
    tunnel = ASGIWebSocketSession(app, "/tunnel/register")
    await tunnel.connect()
    await tunnel.send_text(
        json.dumps(
            {
                "type": "register",
                "connect_code": connect_code,
                "server_id": "srv-1",
                "server_name": "Test LAN Server",
                "token": token,
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


def test_heartbeat_timeout_disconnects_stale_tunnel_and_fails_pending(monkeypatch) -> None:
    monkeypatch.setattr(config, "HEARTBEAT_INTERVAL_SECONDS", 0.05)
    monkeypatch.setattr(config, "HEARTBEAT_TIMEOUT_SECONDS", 0.3)

    async def _run() -> None:
        app = create_router_app()
        tunnel = await _open_registered_tunnel(app, "TEST-HB")

        # Drain ping frames (never replying with a pong) until the heartbeat
        # times out and the router closes the socket.
        for _ in range(50):
            message = await tunnel.receive_raw()
            if message["type"] == "websocket.close":
                assert message.get("code") == 1001
                break
            assert message["type"] == "websocket.send"
            assert json.loads(message["text"])["type"] == "ping"
        else:
            pytest.fail("heartbeat never timed out the tunnel")

        # Let the receive-loop task's cancellation/cleanup finish so the
        # registry deregister has actually happened before we probe it.
        if tunnel._task is not None:
            try:
                await asyncio.wait_for(tunnel._task, timeout=2)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass

        # A request against the now-dead connect code should be treated as
        # offline rather than hanging on the full request timeout.
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/r/TEST-HB/api/health-check")
        assert response.status_code == 503

    asyncio.run(_run())


def test_request_backpressure_returns_503(monkeypatch) -> None:
    monkeypatch.setattr(config, "MAX_PENDING_REQUESTS_PER_TUNNEL", 1)

    async def _run() -> None:
        app = create_router_app()
        tunnel = await _open_registered_tunnel(app, "TEST-BP")

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            first = asyncio.create_task(client.get("/r/TEST-BP/api/slow-1"))
            await tunnel.receive_text()  # first request frame, left pending so the cap stays hit

            second = await client.get("/r/TEST-BP/api/slow-2")
            assert second.status_code == 503

        first.cancel()
        await tunnel.close()

    asyncio.run(_run())


def test_oversized_body_returns_413() -> None:
    async def _run() -> None:
        app = create_router_app()
        tunnel = await _open_registered_tunnel(app, "TEST-413")

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            oversized = b"x" * (config.MAX_REQUEST_BODY_BYTES + 1)
            response = await client.post("/r/TEST-413/api/upload", content=oversized)
        assert response.status_code == 413

        await tunnel.close()

    asyncio.run(_run())


def test_admin_endpoints_require_token(monkeypatch) -> None:
    monkeypatch.setenv("SARAPP_CLOUD_ROUTER_TOKEN", "secret-token")

    async def _run() -> None:
        app = create_router_app()
        tunnel = await _open_registered_tunnel(app, "TEST-ADMIN", token="secret-token")

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            unauthorized = await client.get("/admin/tunnels")
            assert unauthorized.status_code == 401

            authorized = await client.get(
                "/admin/tunnels", headers={"X-Router-Token": "secret-token"}
            )
            assert authorized.status_code == 200
            body = authorized.json()
            assert any(t["connect_code"] == "TEST-ADMIN" for t in body["tunnels"])

            metrics_response = await client.get(
                "/admin/metrics", headers={"X-Router-Token": "secret-token"}
            )
            assert metrics_response.status_code == 200
            assert "active_tunnel_count" in metrics_response.json()

        await tunnel.close()

    asyncio.run(_run())


def test_register_rate_limit_rejects_excess_attempts(monkeypatch) -> None:
    monkeypatch.setattr(config, "REGISTER_RATE_LIMIT_PER_MINUTE", 2)

    async def _run() -> None:
        app = create_router_app()

        # First two registrations from the same host are allowed.
        for i in range(2):
            tunnel = await _open_registered_tunnel(app, f"RL-{i}")
            await tunnel.close()

        # The third should be rejected at the handshake with a close, before
        # any registration ack.
        tunnel = ASGIWebSocketSession(app, "/tunnel/register")
        message = await tunnel.start()
        assert message["type"] == "websocket.close"
        assert message.get("code") == 1013

    asyncio.run(_run())


def test_dashboard_page_served_without_auth() -> None:
    app = create_router_app()
    client = TestClient(app)
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "SARApp Cloud Router" in response.text


def test_dashboard_data_reflects_connected_tunnel_without_auth() -> None:
    async def _run() -> None:
        app = create_router_app()
        tunnel = await _open_registered_tunnel(app, "TEST-DASH")

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # No X-Router-Token header at all - this endpoint must not require it.
            response = await client.get("/dashboard/data")
        assert response.status_code == 200
        body = response.json()
        assert body["active_tunnel_count"] == 1
        assert any(t["connect_code"] == "TEST-DASH" for t in body["tunnels"])
        assert "total_requests" in body["metrics"]

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
