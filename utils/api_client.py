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
from urllib.error import URLError
from urllib.request import Request, urlopen
import json as _json

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://localhost:8765"
_TIMEOUT_SECONDS = 10


class APIError(Exception):
    """Raised when the server returns an error or is unreachable."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class _APIClient:
    """Thin HTTP client that routes all requests to the active SARApp server."""

    def __init__(self) -> None:
        self._base_url: str = _DEFAULT_BASE_URL

    def configure(self, base_url: str) -> None:
        """Point the client at a specific server URL.  Called by the connection
        manager when a server is found or offline mode is entered."""
        self._base_url = base_url.rstrip("/")
        logger.debug("API client configured: %s", self._base_url)

    @property
    def base_url(self) -> str:
        return self._base_url

    # ------------------------------------------------------------------
    # Public request helpers
    # ------------------------------------------------------------------

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        url = self._build_url(path, params)
        req = Request(url, method="GET")
        return self._send(req)

    def post(self, path: str, *, json: Any = None) -> Any:
        return self._request("POST", path, body=json)

    def put(self, path: str, *, json: Any = None) -> Any:
        return self._request("PUT", path, body=json)

    def patch(self, path: str, *, json: Any = None, params: dict[str, Any] | None = None) -> Any:
        return self._request("PATCH", path, body=json, params=params)

    def delete(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        url = self._build_url(path, params)
        req = Request(url, method="DELETE")
        return self._send(req)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, body: Any = None, params: dict[str, Any] | None = None) -> Any:
        url = self._build_url(path, params)
        data = _json.dumps(body).encode("utf-8") if body is not None else None
        req = Request(url, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        return self._send(req)

    def _build_url(self, path: str, params: dict[str, Any] | None = None) -> str:
        url = self._base_url + ("" if path.startswith("/") else "/") + path
        if params:
            from urllib.parse import urlencode
            url += "?" + urlencode({k: v for k, v in params.items() if v is not None})
        return url

    def _send(self, req: Request) -> Any:
        try:
            with urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:
                raw = resp.read()
                if not raw:
                    return None
                return _json.loads(raw)
        except URLError as exc:
            raise APIError(f"Server unreachable: {exc.reason}") from exc
        except Exception as exc:
            status = getattr(getattr(exc, "fp", None), "status", None)
            try:
                body = exc.read().decode("utf-8")  # type: ignore[attr-defined]
                detail = _json.loads(body).get("detail", body)
            except Exception:
                detail = str(exc)
            raise APIError(detail, status_code=status) from exc


# Module-level singleton — import and use directly.
api_client = _APIClient()
