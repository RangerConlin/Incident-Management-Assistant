"""
Program-wide notification emission service.

This is shared infrastructure — not owned by the Planned Events Toolkit or
any other single feature module (see
Design Documents/Instructions/planned_events_phase0_audit.md). Any backend
module may call `emit_notification` to persist a notification and push it to
the right devices; `sarapp_db.services.trigger_engine` (Planned Events'
schedule triggers) is its first caller, not its owner.

Persistence is the source of truth. Push delivery (mobile, via
`sarapp_db.services.push.send_to_person`) is best-effort on top of it — a
push failure (including Firebase being unconfigured in dev/offline
environments) never blocks a notification from being recorded.

Two client-facing delivery channels this deliberately does NOT replace:
each client (desktop today; web/mobile later) keeps its own local
notification module that can independently generate notifications from
changes it observes locally (see `notifications/services/notifier.py` on the
desktop side). This service's job is specifically to push notifications out
to the appropriate place(s) — starting with mobile, since that's the one
channel with no client-local fallback.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.int_id import _ensure_int_ids, next_int_id
from sarapp_db.mongo.repository import BaseRepository
from sarapp_db.services import push
from sarapp_db.services.firebase_client import FirebaseNotConfiguredError

logger = logging.getLogger(__name__)


class NotificationsRepository(BaseRepository):
    collection_name = IncidentCollections.NOTIFICATIONS


def _repo(incident_id: str) -> NotificationsRepository:
    return NotificationsRepository(get_incident_db(incident_id))


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_member_ids(raw: Any) -> List[int]:
    """Parse a team's member list, stored as a JSON string or a plain list."""
    if isinstance(raw, list):
        values = raw
    elif isinstance(raw, str) and raw.strip():
        try:
            values = json.loads(raw)
        except ValueError:
            return []
    else:
        return []
    result: List[int] = []
    for value in values:
        try:
            result.append(int(value))
        except (TypeError, ValueError):
            continue
    return result


def _resolve_audience(
    incident_id: str,
    *,
    audience_role: Optional[str],
    audience_user_id: Optional[int],
    audience_team_id: Optional[int],
) -> List[int]:
    """Resolve targeting fields to a deduplicated list of person_record ids."""
    db = get_incident_db(incident_id)
    person_records: List[int] = []

    if audience_user_id is not None:
        person_records.append(int(audience_user_id))

    if audience_role:
        personnel_col = db[IncidentCollections.INCIDENT_PERSONNEL]
        for doc in personnel_col.find({"role": audience_role, "person_record": {"$exists": True}}):
            person_records.append(int(doc["person_record"]))

    if audience_team_id is not None:
        team_col = db[IncidentCollections.TEAMS]
        team_doc = team_col.find_one({"int_id": int(audience_team_id)})
        if team_doc:
            members = (
                team_doc.get("members_json")
                or team_doc.get("member_person_records")
                or team_doc.get("member_personnel_ids")
            )
            person_records.extend(_parse_member_ids(members))

    seen: set[int] = set()
    deduped: List[int] = []
    for record in person_records:
        if record in seen:
            continue
        seen.add(record)
        deduped.append(record)
    return deduped


def emit_notification(
    incident_id: str,
    *,
    title: str,
    message: str,
    source_type: str,
    source_id: str,
    severity: str = "routine",
    category: str = "operations",
    source_label: Optional[str] = None,
    audience_role: Optional[str] = None,
    audience_user_id: Optional[int] = None,
    audience_team_id: Optional[int] = None,
    requires_acknowledgement: bool = False,
) -> Dict[str, Any]:
    """
    Persist a notification and push it to every resolved recipient's devices.

    Returns the stored document. Push delivery is attempted for every
    resolved person_record but never raises — see module docstring.
    """
    repo = _repo(incident_id)
    _ensure_int_ids(repo._col, "notification_id")
    notification_id = next_int_id(repo._col, "notification_id")

    doc = repo.insert_one(
        {
            "notification_id": notification_id,
            "incident_id": incident_id,
            "title": title,
            "message": message,
            "severity": severity,
            "category": category,
            "source_type": source_type,
            "source_id": source_id,
            "source_label": source_label,
            "audience_role": audience_role,
            "audience_user_id": audience_user_id,
            "audience_team_id": audience_team_id,
            "requires_acknowledgement": requires_acknowledgement,
            "read": False,
        }
    )

    recipients = _resolve_audience(
        incident_id,
        audience_role=audience_role,
        audience_user_id=audience_user_id,
        audience_team_id=audience_team_id,
    )
    delivery: Dict[str, Any] = {"recipients": recipients, "push_sent": 0, "push_attempted": 0}
    for person_record in recipients:
        try:
            summary = push.send_to_person(
                person_record,
                title,
                message,
                data={
                    "notification_id": str(notification_id),
                    "incident_id": incident_id,
                    "source_type": source_type,
                    "source_id": source_id,
                },
            )
            delivery["push_attempted"] += summary.get("attempted", 0)
            delivery["push_sent"] += summary.get("sent", 0)
        except FirebaseNotConfiguredError:
            logger.info("Push not configured; skipping mobile delivery for notification %s.", notification_id)
        except Exception:
            logger.exception("Push delivery failed for notification %s, person_record=%s", notification_id, person_record)

    repo.update_one(doc["_id"], {"delivery": delivery}, touch_updated_at=False)
    doc["delivery"] = delivery
    return doc


def acknowledge_notification(incident_id: str, notification_id: int, *, by: str) -> Optional[Dict[str, Any]]:
    repo = _repo(incident_id)
    doc = repo.find_one({"notification_id": notification_id})
    if doc is None:
        return None
    repo.update_one(doc["_id"], {"acknowledged_at": _utcnow(), "acknowledged_by": by, "read": True})
    return repo.find_one({"notification_id": notification_id})


def dismiss_notification(incident_id: str, notification_id: int, *, by: str) -> Optional[Dict[str, Any]]:
    repo = _repo(incident_id)
    doc = repo.find_one({"notification_id": notification_id})
    if doc is None:
        return None
    repo.update_one(doc["_id"], {"dismissed_at": _utcnow(), "dismissed_by": by, "read": True})
    return repo.find_one({"notification_id": notification_id})


def list_notifications(
    incident_id: str,
    *,
    audience_role: Optional[str] = None,
    audience_user_id: Optional[int] = None,
    unread_only: bool = False,
    source_type: Optional[str] = None,
    source_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    repo = _repo(incident_id)
    query: Dict[str, Any] = {}
    if audience_role:
        query["audience_role"] = audience_role
    if audience_user_id is not None:
        query["audience_user_id"] = int(audience_user_id)
    if unread_only:
        query["read"] = False
    if source_type:
        query["source_type"] = source_type
    if source_id:
        query["source_id"] = source_id
    return repo.find_many(query, sort=[("created_at", -1)])
