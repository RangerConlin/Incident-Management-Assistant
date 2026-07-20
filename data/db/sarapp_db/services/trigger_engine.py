"""
Schedule-trigger evaluation engine.

Reads `ScheduleTrigger` definitions — currently only produced by the Planned
Events Toolkit's `planned_schedule_triggers` collection
(`sarapp_db.api.routers.plannedtoolkit`) — and, for every trigger whose time
has come, emits a notification via `sarapp_db.services.notification_service`.

This module intentionally lives in the shared `services/` tier, not under
`modules/plannedtoolkit`: the toolkit owns trigger *definitions*, this engine
owns *evaluation and delivery*, so a different trigger source could plug into
the same evaluation loop later without moving code. See
Design Documents/Instructions/planned_events_phase0_audit.md, section 3.2.

Scope note: recurring triggers are intentionally skipped. No shared
recurrence/date-time utility exists in the codebase yet (see the audit
above); building a bespoke one just for this engine would repeat a mistake
the audit already flagged. Only one-shot triggers are evaluated.

Idempotency: a trigger is marked with `fired_at` the moment it's evaluated as
due, and is never re-queried once that field is set. Only one `lan_server`
process runs per incident in this architecture, so a stronger distributed
lock isn't needed for this slice.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sarapp_db.api.routers.ic_overview import list_incidents
from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.services import notification_service

logger = logging.getLogger(__name__)

_CLOSED_STATUSES = {"closed", "archived"}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_trigger_at(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _optional_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _fire_trigger(col, trigger: Dict[str, Any], incident_id: str) -> None:
    title = trigger.get("title") or trigger.get("label") or "Scheduled reminder"
    message = trigger.get("message_template") or trigger.get("summary") or title

    notification_service.emit_notification(
        incident_id,
        title=title,
        message=message,
        source_type="planned_schedule_trigger",
        source_id=str(trigger.get("trigger_id", "")),
        source_label=trigger.get("label"),
        audience_role=trigger.get("audience_role") or None,
        audience_user_id=_optional_int(trigger.get("audience_user_id")),
        audience_team_id=_optional_int(trigger.get("assigned_team_id")),
        requires_acknowledgement=bool(trigger.get("requires_acknowledgement", False)),
    )
    col.update_one({"_id": trigger["_id"]}, {"$set": {"fired_at": _utcnow()}})


def evaluate_due_triggers(incident_id: str) -> int:
    """Fire every due, non-recurring, not-yet-fired trigger for one incident.

    Returns the number of triggers fired.
    """
    db = get_incident_db(incident_id)
    col = db[IncidentCollections.PLANNED_SCHEDULE_TRIGGERS]

    now = datetime.now(timezone.utc)
    fired = 0
    for trigger in col.find(
        {
            "enabled": {"$ne": False},
            "recurring": {"$ne": True},
            "fired_at": {"$exists": False},
        }
    ):
        due_at = _parse_trigger_at(trigger.get("trigger_at"))
        if due_at is None or due_at > now:
            continue
        try:
            _fire_trigger(col, trigger, incident_id)
            fired += 1
        except Exception:
            logger.exception(
                "Failed to fire schedule trigger %s for incident %s",
                trigger.get("trigger_id"),
                incident_id,
            )
    return fired


def evaluate_all_incidents() -> int:
    """Evaluate due triggers across every non-closed incident.

    Called once per poll-loop tick from lan_server. Returns the total number
    of triggers fired across all incidents.
    """
    total = 0
    for incident in list_incidents():
        status = str(incident.get("status", "")).lower()
        if status in _CLOSED_STATUSES:
            continue
        incident_id = incident.get("id") or incident.get("incident_id")
        if not incident_id:
            continue
        try:
            total += evaluate_due_triggers(str(incident_id))
        except Exception:
            logger.exception("Failed to evaluate schedule triggers for incident %s", incident_id)
    return total
