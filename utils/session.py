from __future__ import annotations

import socket
import threading
from typing import Any

from utils.audit import write_audit
from utils.state import AppState

# The server sweeps sessions whose last_seen_at is older than its active
# window (5 minutes), so beat well inside that.
_HEARTBEAT_INTERVAL_SECONDS = 60.0

_heartbeat_stop: threading.Event | None = None


def _start_heartbeat(session_id: str) -> None:
    """Keep the server-side session fresh until logout or session change."""

    global _heartbeat_stop
    _stop_heartbeat()
    stop = threading.Event()
    _heartbeat_stop = stop

    def run() -> None:
        from utils.api_client import api_client

        while not stop.wait(_HEARTBEAT_INTERVAL_SECONDS):
            if AppState.get_active_api_session_id() != session_id:
                return
            try:
                api_client.post(f"/api/auth/sessions/{session_id}/heartbeat")
            except Exception:
                # Transient network/server issues: keep trying while the
                # session is active; the server sweep handles true death.
                pass

    threading.Thread(target=run, name="sarapp-session-heartbeat", daemon=True).start()


def _stop_heartbeat() -> None:
    global _heartbeat_stop
    if _heartbeat_stop is not None:
        _heartbeat_stop.set()
        _heartbeat_stop = None


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
            _start_heartbeat(str(session_id))
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
    _stop_heartbeat()
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
