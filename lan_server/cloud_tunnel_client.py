"""Reverse-tunnel client that connects a LAN server to a cloud router.

The LAN server dials *out* to the cloud router (reverse tunnel) so incident
command posts behind NAT with no inbound port-forwarding can still be reached
by field/remote devices. Once registered under a connect code, the cloud
router forwards field-device HTTP requests and WebSocket traffic down this
one persistent connection; this client dispatches them against the LAN
server's own FastAPI app over loopback and sends the results back.

See ``Design Documents/Instructions/cloud_router_architecture.md`` for the
full tunnel frame protocol.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import random
import string
import threading
from typing import Any

import httpx
import websockets

logger = logging.getLogger(__name__)

_ROUTER_URL_ENV_VAR = "SARAPP_CLOUD_ROUTER_URL"
_ROUTER_TOKEN_ENV_VAR = "SARAPP_CLOUD_ROUTER_TOKEN"
_CONNECT_CODE_ENV_VAR = "SARAPP_CONNECT_CODE"

_MIN_BACKOFF_SECONDS = 1.0
_MAX_BACKOFF_SECONDS = 30.0
_AUTH_REJECTION_BACKOFF_SECONDS = 60.0
_REGISTER_TIMEOUT_SECONDS = 10.0


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


# Mirrors cloud_server/router/config.py so both sides of the tunnel agree on
# limits without needing separate env vars.
_REQUEST_TIMEOUT_SECONDS = _float_env("SARAPP_ROUTER_REQUEST_TIMEOUT_SECONDS", 30.0)
_MAX_REQUEST_BODY_BYTES = _int_env("SARAPP_ROUTER_MAX_BODY_BYTES", 20 * 1024 * 1024)
_MAX_CONCURRENT_FRAMES = _int_env("SARAPP_ROUTER_MAX_PENDING_REQUESTS", 200)

# WebSocket close codes the router uses to signal *why* a tunnel was closed
# (see cloud_server/router/app.py); 1008 = policy violation (auth rejected).
_AUTH_REJECTED_CLOSE_CODE = 1008

# Headers that must be recomputed by the loopback HTTP client rather than
# forwarded verbatim from the original field-device request.
_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-length",
    "host",
}


def get_cloud_router_url() -> str | None:
    """Read the cloud router's tunnel-registration URL from the environment."""

    url = os.environ.get(_ROUTER_URL_ENV_VAR, "").strip()
    return url or None


def get_cloud_router_token() -> str | None:
    """Read the shared secret proving this LAN server may register a tunnel."""

    token = os.environ.get(_ROUTER_TOKEN_ENV_VAR, "").strip()
    return token or None


def get_connect_code() -> str | None:
    """Read the operator-supplied connect code, if one was configured."""

    code = os.environ.get(_CONNECT_CODE_ENV_VAR, "").strip()
    return code or None


def generate_connect_code() -> str:
    """Produce a short human-shareable code, e.g. ``ABCD-1234``."""

    letters = "".join(random.choices(string.ascii_uppercase, k=4))
    digits = "".join(random.choices(string.digits, k=4))
    return f"{letters}-{digits}"


def _filtered_headers(headers: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() not in _HOP_BY_HOP_HEADERS}


class CloudTunnelClient:
    """Owns the persistent reverse-tunnel connection to a cloud router."""

    def __init__(
        self,
        *,
        local_port: int,
        server_id: str,
        server_name: str,
        cloud_router_url: str | None = None,
        token: str | None = None,
        connect_code: str | None = None,
    ) -> None:
        self.local_port = local_port
        self.server_id = server_id
        self.server_name = server_name
        self.cloud_router_url = cloud_router_url
        self.token = token
        self.connect_code = connect_code or generate_connect_code()

        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event: asyncio.Event | None = None
        self._ws_channels: dict[str, Any] = {}
        self._frame_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_FRAMES)

    @property
    def enabled(self) -> bool:
        return bool(self.cloud_router_url)

    @property
    def connected(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if not self.enabled:
            logger.info("Cloud tunnel disabled (%s not set)", _ROUTER_URL_ENV_VAR)
            return
        if self._thread and self._thread.is_alive():
            return
        logger.info(
            "Starting cloud tunnel - connect code: %s (share this with field devices)",
            self.connect_code,
        )
        self._thread = threading.Thread(
            target=self._thread_main,
            name="sarapp-cloud-tunnel",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        loop = self._loop
        stop_event = self._stop_event
        if loop is None or stop_event is None:
            return
        loop.call_soon_threadsafe(stop_event.set)
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._run())
        finally:
            loop.close()

    async def _run(self) -> None:
        self._stop_event = asyncio.Event()
        backoff = _MIN_BACKOFF_SECONDS
        while not self._stop_event.is_set():
            auth_rejected = False
            try:
                await self._connect_once()
                backoff = _MIN_BACKOFF_SECONDS
            except Exception as exc:  # noqa: BLE001 - never let the tunnel thread die
                close_code = getattr(exc, "code", None)
                close_reason = getattr(exc, "reason", None)
                if close_code == _AUTH_REJECTED_CLOSE_CODE:
                    auth_rejected = True
                    logger.warning(
                        "Cloud tunnel registration rejected (auth) - backing off %.0fs: %s",
                        _AUTH_REJECTION_BACKOFF_SECONDS,
                        exc,
                    )
                else:
                    logger.warning(
                        "Cloud tunnel connection failed (close_code=%s reason=%s): %s",
                        close_code,
                        close_reason,
                        exc,
                    )
            if self._stop_event.is_set():
                break
            wait_seconds = _AUTH_REJECTION_BACKOFF_SECONDS if auth_rejected else backoff
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=wait_seconds)
            except asyncio.TimeoutError:
                pass
            backoff = _AUTH_REJECTION_BACKOFF_SECONDS if auth_rejected else min(backoff * 2, _MAX_BACKOFF_SECONDS)

    async def _connect_once(self) -> None:
        async with websockets.connect(self.cloud_router_url) as tunnel:
            await tunnel.send(
                json.dumps(
                    {
                        "type": "register",
                        "connect_code": self.connect_code,
                        "server_id": self.server_id,
                        "server_name": self.server_name,
                        "token": self.token or "",
                    }
                )
            )
            ack_raw = await asyncio.wait_for(tunnel.recv(), timeout=_REGISTER_TIMEOUT_SECONDS)
            ack = json.loads(ack_raw)
            if ack.get("type") != "registered":
                raise RuntimeError(f"cloud router rejected registration: {ack}")
            logger.info("Cloud tunnel registered under connect code %s", self.connect_code)

            self._ws_channels = {}
            try:
                await self._pump(tunnel)
            finally:
                await self._close_all_channels()

    async def _close_all_channels(self) -> None:
        channels, self._ws_channels = self._ws_channels, {}
        for local_ws in channels.values():
            try:
                await local_ws.close()
            except Exception:  # noqa: BLE001
                pass

    async def _pump(self, tunnel: Any) -> None:
        self._frame_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_FRAMES)
        async for raw in tunnel:
            try:
                frame = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            frame_type = frame.get("type")
            if frame_type == "request":
                self._spawn_bounded(self._handle_request(tunnel, frame))
            elif frame_type == "ws_open":
                self._spawn_bounded(self._handle_ws_open(tunnel, frame))
            elif frame_type == "ws_message":
                self._spawn_bounded(self._handle_ws_message(frame))
            elif frame_type == "ws_close":
                self._spawn_bounded(self._handle_ws_close(frame))
            elif frame_type == "ping":
                asyncio.create_task(self._send_pong(tunnel, frame.get("ts")))
            else:
                logger.warning("Ignoring unrecognized tunnel frame type: %r", frame_type)

    async def _send_pong(self, tunnel: Any, ts: Any) -> None:
        try:
            await tunnel.send(json.dumps({"type": "pong", "ts": ts}))
        except Exception:  # noqa: BLE001 - tunnel may be tearing down; nothing to do
            pass

    def _spawn_bounded(self, coro: Any) -> None:
        async def _run_bounded() -> None:
            async with self._frame_semaphore:
                await coro

        asyncio.create_task(_run_bounded())

    async def _handle_request(self, tunnel: Any, frame: dict[str, Any]) -> None:
        request_id = frame.get("request_id")
        method = frame.get("method", "GET")
        path = frame.get("path", "/")
        query = frame.get("query") or ""
        headers = _filtered_headers(frame.get("headers") or {})
        body_b64 = frame.get("body")
        body = base64.b64decode(body_b64) if body_b64 else b""

        if len(body) > _MAX_REQUEST_BODY_BYTES:
            logger.warning(
                "Rejecting oversized request body (%d bytes) for %s %s", len(body), method, path
            )
            await tunnel.send(
                json.dumps(
                    {
                        "type": "response",
                        "request_id": request_id,
                        "status": 413,
                        "headers": {},
                        "body": base64.b64encode(b"Request body too large").decode("ascii"),
                    }
                )
            )
            return

        url = f"http://127.0.0.1:{self.local_port}{path}"
        if query:
            url = f"{url}?{query}"

        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.request(method, url, headers=headers, content=body)
            response_frame = {
                "type": "response",
                "request_id": request_id,
                "status": response.status_code,
                "headers": dict(response.headers),
                "body": base64.b64encode(response.content).decode("ascii"),
            }
        except Exception as exc:  # noqa: BLE001 - report as a proxy error, don't crash the tunnel
            logger.warning("Loopback request failed for %s %s: %s", method, path, exc)
            response_frame = {
                "type": "response",
                "request_id": request_id,
                "status": 502,
                "headers": {},
                "body": base64.b64encode(str(exc).encode("utf-8")).decode("ascii"),
            }
        await tunnel.send(json.dumps(response_frame))

    async def _handle_ws_open(self, tunnel: Any, frame: dict[str, Any]) -> None:
        channel_id = frame.get("channel_id")
        path = frame.get("path", "/")
        url = f"ws://127.0.0.1:{self.local_port}{path}"
        try:
            local_ws = await websockets.connect(url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to open local websocket for channel %s: %s", channel_id, exc)
            await tunnel.send(json.dumps({"type": "ws_close", "channel_id": channel_id}))
            return
        self._ws_channels[channel_id] = local_ws
        asyncio.create_task(self._pump_local_channel(tunnel, channel_id, local_ws))

    async def _pump_local_channel(self, tunnel: Any, channel_id: str, local_ws: Any) -> None:
        try:
            async for message in local_ws:
                is_binary = isinstance(message, (bytes, bytearray))
                await tunnel.send(
                    json.dumps(
                        {
                            "type": "ws_message",
                            "channel_id": channel_id,
                            "binary": is_binary,
                            "data": base64.b64encode(message).decode("ascii") if is_binary else message,
                        }
                    )
                )
        except Exception:  # noqa: BLE001 - normal on disconnect
            pass
        finally:
            self._ws_channels.pop(channel_id, None)
            try:
                await tunnel.send(json.dumps({"type": "ws_close", "channel_id": channel_id}))
            except Exception:  # noqa: BLE001
                pass

    async def _handle_ws_message(self, frame: dict[str, Any]) -> None:
        channel_id = frame.get("channel_id")
        local_ws = self._ws_channels.get(channel_id)
        if local_ws is None:
            return
        data = frame.get("data", "")
        try:
            if frame.get("binary"):
                await local_ws.send(base64.b64decode(data))
            else:
                await local_ws.send(data)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to forward ws message on channel %s: %s", channel_id, exc)

    async def _handle_ws_close(self, frame: dict[str, Any]) -> None:
        channel_id = frame.get("channel_id")
        local_ws = self._ws_channels.pop(channel_id, None)
        if local_ws is not None:
            try:
                await local_ws.close()
            except Exception:  # noqa: BLE001
                pass
