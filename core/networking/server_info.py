"""Shared SARApp incident server connection constants and helpers."""

from __future__ import annotations

DEFAULT_SERVER_HOST = "127.0.0.1"
DEFAULT_SERVER_PORT = 8765
HEALTH_PATH = "/health"
SARAPP_SERVICE_ID = "sarapp"
DEFAULT_LOCAL_SERVER_NAME = "Local SARApp Server"


def build_base_url(host: str, port: int) -> str:
    """Return a normalized HTTP base URL for a SARApp incident server."""
    cleaned_host = str(host).strip()
    if cleaned_host.startswith("http://") or cleaned_host.startswith("https://"):
        return cleaned_host.rstrip("/")
    return f"http://{cleaned_host}:{int(port)}"


def is_sarapp_health_payload(payload: object) -> bool:
    """Return True when a /health response looks like a SARApp server."""
    if not isinstance(payload, dict):
        return False
    status = str(payload.get("status", "")).lower()
    service = str(payload.get("service", payload.get("app", ""))).lower()
    return status in {"ok", "healthy"} and service == SARAPP_SERVICE_ID
