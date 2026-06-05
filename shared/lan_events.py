from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

INCIDENT_SNAPSHOT = "incident.snapshot"
TEAM_UPDATED = "team.updated"
TEAM_STATUS_CHANGED = "team.status_changed"
TASK_CREATED = "task.created"
TASK_UPDATED = "task.updated"
TASK_STATUS_CHANGED = "task.status_changed"
COMMS_CREATED = "comms.created"
ALERT_CREATED = "alert.created"
CONNECTION_STATE = "connection.state"


def make_event(event_type: str, payload: dict[str, Any], *, source: str = "host") -> dict[str, Any]:
    return {
        "type": str(event_type),
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
    }
