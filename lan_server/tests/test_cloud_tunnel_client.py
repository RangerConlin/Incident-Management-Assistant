"""Unit tests for the LAN-side reverse-tunnel client's frame handling.

These drive ``CloudTunnelClient._pump``/``_handle_request`` directly against
a fake tunnel object rather than opening a real WebSocket, matching the
level these methods actually operate at (frame in, frame out).
"""

from __future__ import annotations

import asyncio
import base64
import json

import pytest

from lan_server.cloud_tunnel_client import CloudTunnelClient


class _FakeTunnel:
    def __init__(self, frames: list[dict]) -> None:
        self._frames = frames
        self.sent: list[dict] = []

    def __aiter__(self):
        return self._aiter()

    async def _aiter(self):
        for frame in self._frames:
            yield json.dumps(frame)

    async def send(self, raw: str) -> None:
        self.sent.append(json.loads(raw))


def _make_client(**overrides) -> CloudTunnelClient:
    defaults = dict(local_port=9999, server_id="s1", server_name="Test Server")
    defaults.update(overrides)
    return CloudTunnelClient(**defaults)


def test_pump_replies_to_ping_with_pong() -> None:
    async def _run() -> None:
        client = _make_client()
        tunnel = _FakeTunnel([{"type": "ping", "ts": 123.45}])
        await client._pump(tunnel)
        await asyncio.sleep(0)  # let the fire-and-forget pong send land
        assert {"type": "pong", "ts": 123.45} in tunnel.sent

    asyncio.run(_run())


def test_pump_ignores_unknown_frame_type_without_raising(caplog) -> None:
    async def _run() -> None:
        client = _make_client()
        tunnel = _FakeTunnel([{"type": "something_new", "data": "x"}])
        await client._pump(tunnel)  # must not raise

    asyncio.run(_run())


def test_handle_request_rejects_oversized_body(monkeypatch) -> None:
    import lan_server.cloud_tunnel_client as tunnel_module

    monkeypatch.setattr(tunnel_module, "_MAX_REQUEST_BODY_BYTES", 4)

    async def _run() -> None:
        client = _make_client()
        tunnel = _FakeTunnel([])
        oversized_body = base64.b64encode(b"way too big").decode("ascii")
        frame = {
            "request_id": "r1",
            "method": "POST",
            "path": "/api/upload",
            "query": "",
            "headers": {},
            "body": oversized_body,
        }
        await client._handle_request(tunnel, frame)
        assert len(tunnel.sent) == 1
        assert tunnel.sent[0]["status"] == 413
        assert tunnel.sent[0]["request_id"] == "r1"

    asyncio.run(_run())


def test_handle_request_rejects_oversized_response(monkeypatch) -> None:
    import lan_server.cloud_tunnel_client as tunnel_module

    monkeypatch.setattr(tunnel_module, "_MAX_REQUEST_BODY_BYTES", 4)

    class _FakeResponse:
        status_code = 200
        headers: dict = {}
        content = b"way too big"

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self) -> "_FakeAsyncClient":
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def request(self, *args, **kwargs) -> _FakeResponse:
            return _FakeResponse()

    monkeypatch.setattr(tunnel_module.httpx, "AsyncClient", _FakeAsyncClient)

    async def _run() -> None:
        client = _make_client()
        tunnel = _FakeTunnel([])
        frame = {
            "request_id": "r2",
            "method": "GET",
            "path": "/api/download",
            "query": "",
            "headers": {},
            "body": "",
        }
        await client._handle_request(tunnel, frame)
        assert len(tunnel.sent) == 1
        assert tunnel.sent[0]["status"] == 413
        assert tunnel.sent[0]["request_id"] == "r2"

    asyncio.run(_run())


def test_spawn_bounded_limits_concurrency() -> None:
    async def _run() -> None:
        client = _make_client()
        client._frame_semaphore = asyncio.Semaphore(2)
        running = 0
        max_running = 0
        started = asyncio.Event()

        async def _task() -> None:
            nonlocal running, max_running
            running += 1
            max_running = max(max_running, running)
            started.set()
            await asyncio.sleep(0.05)
            running -= 1

        for _ in range(5):
            client._spawn_bounded(_task())
        await asyncio.sleep(0.2)
        assert max_running <= 2

    asyncio.run(_run())


def test_auth_rejected_close_code_constant_matches_router_policy_violation() -> None:
    import lan_server.cloud_tunnel_client as tunnel_module

    # The router closes registration with code 1008 (WS policy violation) on
    # a bad token; the LAN client must recognize that exact code to apply
    # its longer auth-rejection backoff instead of the normal exponential one.
    assert tunnel_module._AUTH_REJECTED_CLOSE_CODE == 1008
