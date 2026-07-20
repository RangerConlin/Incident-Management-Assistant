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
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:8765"
_DEFAULT_BASE_URL = DEFAULT_BASE_URL
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

    def configure_test_transport(self, app: Any) -> None:
        """Route requests in-process to an ASGI app instead of over the network.

        Test-only: lets modules that call api_client be tested against the real
        FastAPI app (e.g. sarapp_db.api.app.create_app()) without a server
        process actually listening on a port. Call configure(...) afterward to
        point back at a real server.

        Uses Starlette's TestClient rather than a plain httpx.Client +
        ASGITransport: httpx's ASGITransport is async-only, but api_client is
        a sync client throughout the app; TestClient wraps the same transport
        with a background event-loop portal so synchronous calls work.
        """
        from starlette.testclient import TestClient

        try:
            self._client.close()
        except Exception:
            pass
        self._base_url = "http://testserver"
        self._client = TestClient(app, base_url=self._base_url)

    @property
    def base_url(self) -> str:
        return self._base_url

    # ------------------------------------------------------------------
    # Public request helpers
    # ------------------------------------------------------------------

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return self._send("GET", path, params=params)

    def post(self, path: str, *, json: Any = None, params: dict[str, Any] | None = None) -> Any:
        return self._send("POST", path, json=json, params=params)

    def put(self, path: str, *, json: Any = None, params: dict[str, Any] | None = None) -> Any:
        return self._send("PUT", path, json=json, params=params)

    def patch(self, path: str, *, json: Any = None, params: dict[str, Any] | None = None) -> Any:
        return self._send("PATCH", path, json=json, params=params)

    def delete(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return self._send("DELETE", path, params=params)

    def post_file(
        self,
        path: str,
        *,
        file_path: str,
        field_name: str = "file",
        data: dict[str, Any] | None = None,
    ) -> Any:
        """POST a file as multipart/form-data, with the rest of ``data`` as form fields."""
        url = self._build_url(path)
        form_data = {k: v for k, v in (data or {}).items() if v is not None}
        with open(file_path, "rb") as fh:
            files = {field_name: (Path(file_path).name, fh)}
            try:
                resp = self._client.request("POST", url, data=form_data, files=files)
            except httpx.TransportError as exc:
                raise APIError(f"Server unreachable: {exc}") from exc
            except Exception as exc:
                raise APIError(f"Request failed: {exc}") from exc
        return self._handle_response(resp)

    def get_bytes(self, path: str, *, params: dict[str, Any] | None = None) -> bytes:
        """GET a binary response body (e.g. a file download)."""
        url = self._build_url(path)
        if params:
            params = {k: v for k, v in params.items() if v is not None}
        try:
            resp = self._request_with_retry("GET", url, json=None, params=params)
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
        return resp.content

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_url(self, path: str) -> str:
        return self._base_url + ("" if path.startswith("/") else "/") + path

    def _request_with_retry(
        self, method: str, url: str, *, json: Any, params: dict[str, Any] | None
    ) -> httpx.Response:
        """Send a request, retrying once on a stale pooled connection.

        The server's keep-alive timeout can expire and close an idle socket
        before httpx's connection pool (configured to never expire client-side)
        notices, so the first write on a reused connection can land on an
        already-closed socket with no response. Retrying once with a fresh
        connection resolves it without masking real server-down errors.
        """
        try:
            return self._client.request(method, url, json=json, params=params or None)
        except httpx.RemoteProtocolError:
            return self._client.request(method, url, json=json, params=params or None)

    def _send(self, method: str, path: str, *, json: Any = None, params: dict[str, Any] | None = None) -> Any:
        url = self._build_url(path)
        if params:
            params = {k: v for k, v in params.items() if v is not None}
        try:
            resp = self._request_with_retry(method, url, json=json, params=params)
        except httpx.TransportError as exc:
            raise APIError(f"Server unreachable: {exc}") from exc
        except Exception as exc:
            raise APIError(f"Request failed: {exc}") from exc

        return self._handle_response(resp)

    def _handle_response(self, resp: httpx.Response) -> Any:
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
