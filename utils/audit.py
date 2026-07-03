from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_audit(
    action: str,
    detail: Optional[Dict[str, Any]] = None,
    *,
    prefer_mission: bool = True,
) -> None:
    from utils.api_client import api_client
    from utils.state import AppState

    user = AppState.get_active_user_id()
    incident = AppState.get_active_incident() if prefer_mission else None
    payload: Dict[str, Any] = {
        "action": action,
        "detail": detail,
        "user_id": str(user) if user is not None else None,
        "incident_id": incident,
        "ts_utc": now_utc_iso(),
    }
    try:
        api_client.post("/api/audit", json=payload)
    except Exception:
        pass


def audit_action(action: str, *, prefer_mission: bool = True) -> Callable:
    def decorator(func: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                result = func(*args, **kwargs)
            except Exception as e:
                write_audit(action, {"result": "error", "error": repr(e)}, prefer_mission=prefer_mission)
                raise
            else:
                write_audit(action, {"result": "ok"}, prefer_mission=prefer_mission)
                return result
        return wrapper
    return decorator


def fetch_last_audit_rows(limit: int = 10) -> list[dict[str, Any]]:
    from utils.api_client import api_client
    from utils.state import AppState

    incident_id = AppState.get_active_incident()
    try:
        return api_client.get(
            "/api/audit",
            params={"incident_id": incident_id, "limit": limit} if incident_id else {"limit": limit},
        ) or []
    except Exception:
        return []


__all__ = ["write_audit", "audit_action", "now_utc_iso", "fetch_last_audit_rows"]
