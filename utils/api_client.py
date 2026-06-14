"""SARApp API client.

Single place for all HTTP communication between the desktop UI and the SARApp
server (LAN, cloud, or built-in offline).  Every module calls this instead of
touching a database repository directly.

Usage:
    from utils.api_client import api_client

    data = api_client.get("/api/objectives", params={"incident_id": "2025-FAIR"})
    api_client.post("/api/objectives", json={...})
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://localhost:8765"
_TIMEOUT_SECONDS = 10


class APIError(Exception):
    """Raised when the server returns an error or is unreachable."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class _APIClient:
    """Thin HTTP client that routes all requests to the active SARApp server.

    Uses an httpx.Client so TCP connections are reused across calls — critical
    for detail windows that make 12+ sequential requests on open.
    """

    def __init__(self) -> None:
        self._base_url: str = _DEFAULT_BASE_URL
        self._client = self._make_client()

    def _make_client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self._base_url,
            timeout=_TIMEOUT_SECONDS,
            limits=httpx.Limits(
                max_keepalive_connections=10,
                max_connections=20,
                keepalive_expiry=None,  # never drop idle connections
            ),
        )

    def configure(self, base_url: str) -> None:
        """Point the client at a specific server URL.  Called by the connection
        manager when a server is found or offline mode is entered."""
        self._base_url = base_url.rstrip("/")
        try:
            self._client.close()
        except Exception:
            pass
        self._client = self._make_client()
        logger.debug("API client configured: %s", self._base_url)

    @property
    def base_url(self) -> str:
        return self._base_url

    # ------------------------------------------------------------------
    # Public request helpers
    # ------------------------------------------------------------------

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return self._send("GET", path, params=params)

    def post(self, path: str, *, json: Any = None) -> Any:
        return self._send("POST", path, json=json)

    def put(self, path: str, *, json: Any = None) -> Any:
        return self._send("PUT", path, json=json)

    def patch(self, path: str, *, json: Any = None, params: dict[str, Any] | None = None) -> Any:
        return self._send("PATCH", path, json=json, params=params)

    def delete(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return self._send("DELETE", path, params=params)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_url(self, path: str) -> str:
        return self._base_url + ("" if path.startswith("/") else "/") + path

    def _send(self, method: str, path: str, *, json: Any = None, params: dict[str, Any] | None = None) -> Any:
        url = self._build_url(path)
        if params:
            params = {k: v for k, v in params.items() if v is not None}
        try:
            resp = self._client.request(
                method,
                url,
                json=json,
                params=params or None,
            )
        except httpx.TransportError as exc:
            raise APIError(f"Server unreachable: {exc}") from exc
        except Exception as exc:
            raise APIError(f"Request failed: {exc}") from exc

        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise APIError(str(detail), status_code=resp.status_code)

        if not resp.content:
            return None
        return resp.json()


# Module-level singleton — import and use directly.
api_client = _APIClient()
