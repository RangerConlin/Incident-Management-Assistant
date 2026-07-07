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
import json
import logging
import os
import uuid
from typing import Any, Callable

from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from .registry import TunnelConnection, TunnelUnavailableError, registry

logger = logging.getLogger(__name__)

_TOKEN_ENV_VAR = "SARAPP_CLOUD_ROUTER_TOKEN"
_REQUEST_TIMEOUT_SECONDS = 30.0

# Headers that must be recomputed by the receiving side rather than proxied
# verbatim (matches the filtering done on the LAN-side tunnel client).
_STRIPPED_RESPONSE_HEADERS = {"content-length", "transfer-encoding", "connection", "content-encoding"}


def _expected_token() -> str:
    return os.environ.get(_TOKEN_ENV_VAR, "").strip()


def create_router_app(*, server_info_fn: Callable[[], dict[str, Any]] | None = None) -> FastAPI:
    app = FastAPI(title="SARApp Cloud Router")

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"ok": True, "server": server_info_fn() if server_info_fn else {}}

    @app.get("/server-info")
    async def server_info() -> dict[str, Any]:
        return server_info_fn() if server_info_fn else {}

    @app.websocket("/tunnel/register")
    async def tunnel_register(websocket: WebSocket) -> None:
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
        if expected_token and frame.get("token") != expected_token:
            logger.warning("Rejected tunnel registration with invalid token")
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

        try:
            while True:
                reply_frame = json.loads(await websocket.receive_text())
                reply_type = reply_frame.get("type")
                if reply_type == "response":
                    connection.resolve_response(reply_frame)
                elif reply_type == "ws_message":
                    connection.dispatch_ws_message(reply_frame)
                elif reply_type == "ws_close":
                    connection.dispatch_ws_close(reply_frame)
        except (WebSocketDisconnect, json.JSONDecodeError):
            pass
        finally:
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
        try:
            future = await connection.send_request(
                request_id=request_id,
                method=request.method,
                path=f"/{path}",
                query=request.url.query,
                headers=dict(request.headers),
                body_b64=base64.b64encode(body).decode("ascii"),
            )
            response_frame = await asyncio.wait_for(future, timeout=_REQUEST_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            connection.pending_requests.pop(request_id, None)
            return JSONResponse({"detail": "LAN server timed out"}, status_code=504)
        except TunnelUnavailableError:
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

        await websocket.accept()
        channel_id = uuid.uuid4().hex
        queue = connection.register_ws_channel(channel_id)
        await connection.open_ws_channel(channel_id, f"/{path}")

        async def _pump_downstream() -> None:
            while True:
                item = await queue.get()
                if item.get("type") == "closed":
                    await websocket.close()
                    return
                if item.get("binary"):
                    await websocket.send_bytes(base64.b64decode(item.get("data", "")))
                else:
                    await websocket.send_text(item.get("data", ""))

        downstream_task = asyncio.create_task(_pump_downstream())
        try:
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
            downstream_task.cancel()
            connection.close_ws_channel_locally(channel_id)
            await connection.send_ws_close(channel_id)

    return app
