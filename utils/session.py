from __future__ import annotations

import socket
from typing import Any

from utils.audit import write_audit
from utils.state import AppState


def _start_api_session(
    *,
    user_id: str,
    username: str | None = None,
    display_name: str | None = None,
    role: str | None = None,
    person_record: int | None = None,
    incident_id: str | None = None,
    mode: str | None = None,
) -> str | None:
    try:
        from utils.api_client import api_client

        payload: dict[str, Any] = {
            "user_id": str(user_id),
            "username": str(username or user_id),
            "display_name": display_name or str(username or user_id),
            "badge_number": str(username or user_id),
            "person_record": person_record,
            "role": role or "",
            "incident_id": incident_id,
            "mode": mode or "",
            "status": "online",
            "device_name": socket.gethostname(),
        }
        doc: dict[str, Any] = api_client.post("/api/auth/sessions", json=payload) or {}
        session_id = doc.get("session_id")
        if session_id:
            AppState.set_active_api_session_id(str(session_id))
            return str(session_id)
    except Exception as exc:
        write_audit("presence.session_start_failed", {"error": str(exc)}, prefer_mission=False)
    return None


def start_session(
    user_id: int | str,
    *,
    username: str | None = None,
    display_name: str | None = None,
    role: str | None = None,
    person_record: int | None = None,
    personnel_id: str | None = None,  # legacy param, unused
    incident_id: str | None = None,
    mode: str | None = None,
) -> str | None:
    return _start_api_session(
        user_id=str(user_id),
        username=username,
        display_name=display_name,
        role=role,
        person_record=person_record,
        incident_id=incident_id,
        mode=mode,
    )


def end_session() -> None:
    api_session_id = AppState.get_active_api_session_id()
    if not api_session_id:
        return
    try:
        from utils.api_client import api_client

        api_client.post(f"/api/auth/sessions/{api_session_id}/logout")
    except Exception as exc:
        write_audit("presence.session_end_failed", {"error": str(exc)}, prefer_mission=False)
    finally:
        AppState.set_active_api_session_id(None)


__all__ = ["start_session", "end_session"]
