"""Connect-code path-prefix middleware.

The public URL shape must match the existing cloud connect-code flow:
``/r/<connect_code>/...``. Traefik routes that prefix to this container and
this middleware validates the code, strips the prefix, and lets the normal
SARApp FastAPI app handle the request as if it came from a LAN server root.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from urllib.parse import quote

from starlette.responses import JSONResponse, RedirectResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class ConnectCodePrefixMiddleware:
    def __init__(self, app: ASGIApp, *, connect_code: str) -> None:
        self.app = app
        self.connect_code = connect_code.strip().upper()
        self.prefix = f"/r/{quote(self.connect_code)}"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path") or "")
        if path in {"", "/"} and scope["type"] == "http":
            response = RedirectResponse(f"{self.prefix}/dashboard")
            await response(scope, receive, send)
            return

        # The old cloud router forwards LAN-server traffic to the tunnel client
        # after it has already validated the connect code, so those loopback
        # requests arrive without /r/<code>. Keep the public direct path form
        # working too for optional Traefik access and local diagnostics.
        if self._is_unprefixed_router_path(path):
            await self.app(scope, receive, send)
            return

        if path != self.prefix and not path.startswith(f"{self.prefix}/"):
            response = JSONResponse(
                {"detail": "invalid or missing SARApp connect-code path"},
                status_code=404,
            )
            await response(scope, receive, send)
            return

        stripped = path[len(self.prefix) :] or "/"
        next_scope = dict(scope)
        next_scope["path"] = stripped
        next_scope["root_path"] = self.prefix
        await self.app(next_scope, receive, send)

    @staticmethod
    def _is_unprefixed_router_path(path: str) -> bool:
        if path in {"/health", "/server-info", "/openapi.json", "/docs", "/redoc"}:
            return True
        if path == "/dashboard" or path.startswith("/dashboard/"):
            return True
        return path == "/api" or path.startswith("/api/")

