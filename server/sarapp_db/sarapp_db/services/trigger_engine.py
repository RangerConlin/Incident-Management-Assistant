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
docs/archive/design-documents/Instructions/planned_events_phase0_audit.md, section 3.2.

Scope note: recurring triggers are intentionally skipped. No shared
recurrence/date-time utility exists in the codebase yet (see the audit
above); building a bespoke one just for this engine would repeat a mistake
the audit already flagged. Only one-shot triggers are evaluated.

Idempotency (Phase 1E hardening): claiming a trigger occurrence and firing it
are two separate steps, and only the claim needs to be atomic. `_claim_trigger`
does a single `find_one_and_update` that sets `fired_at` only if it is not
already set, so when two evaluator loops race for the same trigger (this
*does* happen in practice: both `lan_server` and `cloud_server` run their own
`NotificationTriggerLoop` for cloud-connected incidents, contrary to this
module's older docstring, which assumed a single evaluator per incident) at
most one of them gets the claim and the other moves on without emitting.
Emission happens only after a successful claim, so a crash between claim and
emission costs a missed notification, never a duplicate one -- the brief's
explicit requirement. A failed emission after a successful claim is recorded
on the trigger (`fire_error`) rather than retried, for the same reason: retrying
would risk a second notification for an occurrence that may have partially
delivered.
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


def _claim_trigger(col, trigger_doc_id: Any) -> Optional[Dict[str, Any]]:
    """Atomically mark one trigger as fired, returning the claimed document
    only if this call is the one that set `fired_at` -- `None` if another
    evaluator already claimed it first."""
    return col.find_one_and_update(
        {"_id": trigger_doc_id, "fired_at": {"$exists": False}},
        {"$set": {"fired_at": _utcnow()}, "$unset": {"fire_error": ""}},
    )


def _fire_trigger(col, trigger: Dict[str, Any], incident_id: str) -> None:
    """Emit the notification for an already-claimed trigger.

    `fired_at` is already set by `_claim_trigger` before this runs, so a
    failure here is recorded on the trigger (`fire_error`) rather than
    retried -- see module docstring.
    """
    title = trigger.get("title") or trigger.get("label") or "Scheduled reminder"
    message = trigger.get("message_template") or trigger.get("summary") or title

    try:
        notification_service.emit_notification(
            incident_id,
            title=title,
            message=message,
            severity=trigger.get("severity") or "routine",
            source_type="planned_schedule_trigger",
            source_id=str(trigger.get("trigger_id", "")),
            source_label=trigger.get("label"),
            audience_role=trigger.get("audience_role") or None,
            audience_user_id=_optional_int(trigger.get("audience_user_id")),
            audience_team_id=_optional_int(trigger.get("assigned_team_id")),
            requires_acknowledgement=bool(trigger.get("requires_acknowledgement", False)),
        )
    except Exception as exc:
        col.update_one({"_id": trigger["_id"]}, {"$set": {"fire_error": str(exc)[:500]}})
        raise


def evaluate_due_triggers(incident_id: str) -> int:
    """Fire every due, non-recurring, not-yet-fired trigger for one incident.

    Returns the number of triggers fired.
    """
    db = get_incident_db(incident_id)
    col = db[IncidentCollections.PLANNED_SCHEDULE_TRIGGERS]

    now = datetime.now(timezone.utc)
    fired = 0
    candidates = list(col.find(
        {
            "enabled": {"$ne": False},
            "recurring": {"$ne": True},
            "fired_at": {"$exists": False},
        }
    ))
    for trigger in candidates:
        due_at = _parse_trigger_at(trigger.get("trigger_at"))
        if due_at is None or due_at > now:
            continue
        claimed = _claim_trigger(col, trigger["_id"])
        if claimed is None:
            # Another evaluator (a concurrent poll tick, or lan_server and
            # cloud_server racing on the same incident) claimed it first.
            continue
        try:
            _fire_trigger(col, claimed, incident_id)
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

    Called once per poll-loop tick from services/lan_server. Returns the total number
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
