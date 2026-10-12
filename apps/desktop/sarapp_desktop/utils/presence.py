"""Client helpers for user presence/session state.

The backing data is server-owned.  These helpers give desktop modules such as
chat a small API for listing logged-in users and updating the current status.
"""

from __future__ import annotations

from typing import Any

from utils.api_client import api_client
from utils.state import AppState


def list_active_sessions(*, incident_id: str | None = None, include_offline: bool = False) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"include_offline": include_offline}
    if incident_id:
        params["incident_id"] = incident_id
    return api_client.get("/api/auth/sessions/active", params=params) or []


def list_logged_in_users(*, incident_id: str | None = None) -> list[dict[str, Any]]:
    """Return active sessions with resolved user and linked personnel details."""
    return list_active_sessions(incident_id=incident_id)


def update_current_status(status: str) -> dict[str, Any] | None:
    session_id = AppState.get_active_api_session_id()
    if not session_id:
        return None
    return api_client.patch(f"/api/auth/sessions/{session_id}/status", json={"status": status})


__all__ = ["list_active_sessions", "list_logged_in_users", "update_current_status"]
