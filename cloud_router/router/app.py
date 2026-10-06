"""FastAPI app for the cloud router: reverse-tunnel registration plus the
field-device-facing HTTP/WebSocket proxy.

This app never imports ``sarapp_db`` and never talks to MongoDB directly —
all incident data access happens on the LAN server at the far end of the
tunnel. See ``Design Documents/Instructions/cloud_router_architecture.md``
for the full protocol this module implements.
"""

from __future__ import annotations

import asyncio
import base64
import hmac
import json
import logging
import os
import time
import uuid
from typing import Any, Callable

from fastapi import FastAPI, Header, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse

from . import config
from .dashboard import DASHBOARD_HTML
from .metrics import metrics
from .rate_limit import SlidingWindowLimiter
from .registry import TunnelBackpressureError, TunnelConnection, TunnelUnavailableError, registry

logger = logging.getLogger(__name__)

_TOKEN_ENV_VAR = "SARAPP_CLOUD_ROUTER_TOKEN"

# Headers that must be recomputed by the receiving side rather than proxied
# verbatim (matches the filtering done on the LAN-side tunnel client).
_STRIPPED_RESPONSE_HEADERS = {"content-length", "transfer-encoding", "connection", "content-encoding"}


def _expected_token() -> str:
    return os.environ.get(_TOKEN_ENV_VAR, "").strip()


def _token_valid(candidate: str, expected: str) -> bool:
    return hmac.compare_digest(candidate, expected)


def create_router_app(*, server_info_fn: Callable[[], dict[str, Any]] | None = None) -> FastAPI:
    app = FastAPI(title="SARApp Cloud Router")

    # Per-app so each router instance (and each test) gets an isolated window,
    # and so the limit is read from config at app-creation time rather than
    # frozen at import.
    register_limiter = SlidingWindowLimiter(
        max_events=config.REGISTER_RATE_LIMIT_PER_MINUTE, window_seconds=60.0
    )

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"ok": True, "server": server_info_fn() if server_info_fn else {}}

    @app.get("/server-info")
    async def server_info() -> dict[str, Any]:
        return server_info_fn() if server_info_fn else {}

    @app.websocket("/tunnel/register")
    async def tunnel_register(websocket: WebSocket) -> None:
        client_host = websocket.client.host if websocket.client else "unknown"
        if not register_limiter.allow(client_host):
            metrics.total_register_rejections += 1
            logger.warning("Rate-limited tunnel registration attempt from %s", client_host)
            await websocket.close(code=1013)
            return

        await websocket.accept()
        try:
            frame = json.loads(await websocket.receive_text())
        except Exception:  # noqa: BLE001
            await websocket.close(code=1002)
            return

        if frame.get("type") != "register":
            await websocket.close(code=1002)
            return

        expected_token = _expected_token()
        if expected_token and not _token_valid(str(frame.get("token") or ""), expected_token):
            metrics.total_register_rejections += 1
            logger.warning("Rejected tunnel registration with invalid token from %s", client_host)
            await websocket.close(code=1008)
            return

        connect_code = str(frame.get("connect_code") or "")
        if not connect_code:
            await websocket.close(code=1002)
            return

        connection = TunnelConnection(
            connect_code=connect_code,
            server_id=str(frame.get("server_id") or ""),
            server_name=str(frame.get("server_name") or connect_code),
            websocket=websocket,
        )
        registry.register(connection)
        await websocket.send_text(json.dumps({"type": "registered"}))
        logger.info("LAN server registered under connect code %s", connect_code)

        async def _receive_loop() -> None:
            while True:
                reply_frame = json.loads(await websocket.receive_text())
                reply_type = reply_frame.get("type")
                if reply_type == "response":
                    connection.resolve_response(reply_frame)
                elif reply_type == "ws_message":
                    connection.dispatch_ws_message(reply_frame)
                elif reply_type == "ws_close":
                    connection.dispatch_ws_close(reply_frame)
                elif reply_type == "pong":
                    connection.record_pong(reply_frame)

        async def _heartbeat_loop() -> None:
            while True:
                await asyncio.sleep(config.HEARTBEAT_INTERVAL_SECONDS)
                if time.monotonic() - connection.last_pong_at > config.HEARTBEAT_TIMEOUT_SECONDS:
                    metrics.total_heartbeat_timeouts += 1
                    logger.warning(
                        "Tunnel %s idle-timed-out (no pong in %.0fs)",
                        connect_code,
                        config.HEARTBEAT_TIMEOUT_SECONDS,
                    )
                    await websocket.close(code=1001)
                    return
                try:
                    await connection.send_ping()
                except Exception:  # noqa: BLE001 - socket already dead, receive loop will unwind too
                    return

        receive_task = asyncio.create_task(_receive_loop())
        heartbeat_task = asyncio.create_task(_heartbeat_loop())
        try:
            done, pending = await asyncio.wait(
                {receive_task, heartbeat_task}, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                exc = task.exception()
                if exc is not None and not isinstance(exc, (WebSocketDisconnect, json.JSONDecodeError)):
                    raise exc
        finally:
            for task in (receive_task, heartbeat_task):
                task.cancel()
            registry.deregister(connect_code)
            connection.fail_all()
            logger.info("LAN server disconnected (connect code %s)", connect_code)

    @app.api_route(
        "/r/{connect_code}/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
    )
    async def proxy_http(connect_code: str, path: str, request: Request) -> Response:
        connection = registry.get(connect_code)
        if connection is None:
            return JSONResponse({"detail": "LAN server offline"}, status_code=503)

        request_id = uuid.uuid4().hex
        body = await request.body()
        if len(body) > config.MAX_REQUEST_BODY_BYTES:
            metrics.total_request_failures_413 += 1
            logger.warning(
                "Rejected oversized request body (%d bytes) for %s %s [%s]",
                len(body),
                request.method,
                path,
                connect_code,
            )
            return JSONResponse({"detail": "Request body too large"}, status_code=413)

        metrics.total_requests += 1
        headers = dict(request.headers)
        if request.client:
            headers["x-sarapp-client-ip"] = request.client.host
        try:
            future = await connection.send_request(
                request_id=request_id,
                method=request.method,
                path=f"/{path}",
                query=request.url.query,
                headers=headers,
                body_b64=base64.b64encode(body).decode("ascii"),
            )
            response_frame = await asyncio.wait_for(future, timeout=config.REQUEST_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            connection.pending_requests.pop(request_id, None)
            metrics.total_request_timeouts += 1
            logger.warning("LAN server timed out for %s %s [%s]", request.method, path, connect_code)
            return JSONResponse({"detail": "LAN server timed out"}, status_code=504)
        except TunnelBackpressureError:
            metrics.total_request_failures_503 += 1
            logger.warning("LAN server busy (backpressure) for %s %s [%s]", request.method, path, connect_code)
            return JSONResponse({"detail": "LAN server busy"}, status_code=503)
        except TunnelUnavailableError:
            metrics.total_request_failures_503 += 1
            return JSONResponse({"detail": "LAN server disconnected"}, status_code=503)

        headers = {
            key: value
            for key, value in response_frame.get("headers", {}).items()
            if key.lower() not in _STRIPPED_RESPONSE_HEADERS
        }
        body_bytes = base64.b64decode(response_frame.get("body") or "")
        return Response(content=body_bytes, status_code=response_frame.get("status", 502), headers=headers)

    @app.websocket("/r/{connect_code}/{path:path}")
    async def proxy_ws(websocket: WebSocket, connect_code: str, path: str) -> None:
        connection = registry.get(connect_code)
        if connection is None:
            await websocket.close(code=1013)
            return

        channel_id = uuid.uuid4().hex
        try:
            queue = connection.register_ws_channel(channel_id)
        except TunnelBackpressureError:
            metrics.total_request_failures_503 += 1
            logger.warning("LAN server busy (ws channel limit) for %s [%s]", path, connect_code)
            await websocket.close(code=1013)
            return

        await websocket.accept()
        metrics.total_ws_channels_opened += 1

        async def _pump_downstream() -> None:
            while True:
                item = await queue.get()
                if item.get("type") == "closed":
                    await websocket.close(code=item.get("code", 1000), reason=item.get("reason", ""))
                    return
                if item.get("binary"):
                    await websocket.send_bytes(base64.b64decode(item.get("data", "")))
                else:
                    await websocket.send_text(item.get("data", ""))

        downstream_task: asyncio.Task | None = None
        try:
            # Opening the channel sends over the tunnel and can fail if the
            # tunnel just dropped; keep it inside the try so the finally below
            # always cleans up the channel we registered above.
            await connection.open_ws_channel(channel_id, f"/{path}")
            downstream_task = asyncio.create_task(_pump_downstream())
            while True:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    break
                if message.get("text") is not None:
                    await connection.send_ws_message(channel_id, message["text"], binary=False)
                elif message.get("bytes") is not None:
                    encoded = base64.b64encode(message["bytes"]).decode("ascii")
                    await connection.send_ws_message(channel_id, encoded, binary=True)
        except WebSocketDisconnect:
            pass
        finally:
            if downstream_task is not None:
                downstream_task.cancel()
            connection.close_ws_channel_locally(channel_id)
            await connection.send_ws_close(channel_id)

    def _require_admin_token(x_router_token: str | None) -> JSONResponse | None:
        expected_token = _expected_token()
        if not expected_token or not _token_valid(str(x_router_token or ""), expected_token):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return None

    def _tunnel_summaries() -> list[dict[str, Any]]:
        now = time.monotonic()
        return [
            {
                "connect_code": connection.connect_code,
                "server_id": connection.server_id,
                "server_name": connection.server_name,
                "connected_seconds_ago": now - connection.connected_at,
                "last_pong_seconds_ago": now - connection.last_pong_at,
                "pending_request_count": len(connection.pending_requests),
                "ws_channel_count": len(connection.ws_channels),
            }
            for connection in registry.list_connections()
        ]

    @app.get("/admin/tunnels")
    async def admin_tunnels(x_router_token: str | None = Header(default=None)) -> Response:
        unauthorized = _require_admin_token(x_router_token)
        if unauthorized is not None:
            return unauthorized

        return JSONResponse({"tunnels": _tunnel_summaries()})

    @app.get("/admin/metrics")
    async def admin_metrics(x_router_token: str | None = Header(default=None)) -> Response:
        unauthorized = _require_admin_token(x_router_token)
        if unauthorized is not None:
            return unauthorized

        snapshot = metrics.snapshot()
        snapshot["active_tunnel_count"] = registry.active_tunnel_count()
        return JSONResponse(snapshot)

    # --- Read-only status dashboard -----------------------------------
    # Deliberately unauthenticated (unlike /admin/*): connect codes and
    # server names aren't secret on their own (they're already meant to be
    # shared out-of-band per the architecture doc), and this is a
    # read-only summary — no ability to act on a tunnel from here. Uses its
    # own /dashboard/data endpoint rather than reusing /admin/*, so the
    # token-gated admin endpoints are untouched.
    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard_page() -> str:
        return DASHBOARD_HTML

    @app.get("/dashboard/data")
    async def dashboard_data() -> dict[str, Any]:
        snapshot = metrics.snapshot()
        return {
            "active_tunnel_count": registry.active_tunnel_count(),
            "tunnels": _tunnel_summaries(),
            "metrics": snapshot,
        }

    return app
