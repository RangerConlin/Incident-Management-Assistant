"""Bridges incident-wide WebSocket events into local Notifier calls.

Most WebSocket events from the incident hub are collection-change events
consumed by ``IncidentCache`` (see ``utils/incident_ws_client.py``). A
``"notification"``-type event instead represents a priority alert meant for
a specific audience rather than every client. ``IncidentWebSocketClient``
routes those events here instead of into ``IncidentCache.apply_event``.

Two audience shapes share this one event type:
- ``target_sections``: shown only to a client whose active user currently
  holds an ICP staff position under one of the named sections (e.g. an
  urgent intel item alerting everyone under Operations/Planning/
  Intelligence, not just the three section chiefs) — set by callers like
  ``intel.py``'s urgent-intel broadcast.
- ``target_person_records``: shown only to a client whose active user's
  ``person_record`` is in the list — set by
  ``sarapp_db.services.notification_service.emit_notification``, whose
  audience is already resolved to exact person_records server-side (by
  role, team, or explicit user) for mobile push and ack tracking, so the
  desktop toast reuses that same resolved list instead of re-deriving an
  audience from section titles.

An event with neither field is a broadcast-to-all alert and is shown on
every connected client.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable

logger = logging.getLogger(__name__)


def handle_notification_event(incident_id: str, payload: Dict[str, Any]) -> None:
    """Show a local notification if the active user is ICP staff under one of the target sections.

    If ``target_sections`` is absent, the notification is shown to every
    client (a broadcast-to-all alert); otherwise it's shown only on clients
    whose active user currently holds a command-post position (the section
    chief or one of that section's units, e.g. Situation Unit Leader) under
    one of the named sections. Field structure nested under a section — a
    branch, division, or group, and anything deployed beneath one, such as
    an Operations team leader — is deliberately excluded even though it's
    part of the same section, since those roles are in the field, not at
    the ICP.
    """
    try:
        target_person_records = payload.get("target_person_records")
        if target_person_records:
            if not _current_user_in_records(target_person_records):
                return
        else:
            target_sections = payload.get("target_sections")
            if target_sections and not _current_user_under_section(incident_id, target_sections):
                return

        from notifications.models import Notification
        from notifications.services import get_notifier

        get_notifier().notify(Notification(
            title=payload.get("title", "Notification"),
            message=payload.get("message", ""),
            severity=payload.get("severity", "routine"),
            category=payload.get("category", "operations"),
            source=payload.get("source", "System"),
            entity_type=payload.get("entity_type"),
            entity_id=payload.get("entity_id"),
        ))
    except Exception:
        logger.exception("Failed to handle incident notification event")


def _current_user_in_records(target_person_records: Iterable[Any]) -> bool:
    from utils.state import AppState

    uid = AppState.get_active_user_id()
    if not (uid and str(uid).isdigit()):
        return False
    try:
        targets = {int(record) for record in target_person_records}
    except (TypeError, ValueError):
        return False
    return int(uid) in targets


# Classifications that represent deployed field structure rather than
# command-post staff. A position with one of these classifications, or
# nested under one, is excluded even if it's part of a targeted section.
_FIELD_CLASSIFICATIONS = {"branch", "division", "group"}


def _current_user_under_section(incident_id: str, target_sections: Iterable[str]) -> bool:
    from utils.state import AppState

    uid = AppState.get_active_user_id()
    if not (uid and str(uid).isdigit()):
        return False

    from modules.command.incident_organization.controller import IncidentOrganizationController

    org = IncidentOrganizationController(incident_id)
    assignments = org.list_assignments_for_person(int(uid), active_only=True)
    needles = [s.lower() for s in target_sections]

    for assignment in assignments:
        lineage = _ancestor_lineage(org, assignment.position_id)
        if any(classification in _FIELD_CLASSIFICATIONS for _title, classification in lineage):
            continue  # field structure (branch/division/group) or beneath one — not ICP staff
        if any(any(needle in title.lower() for needle in needles) for title, _classification in lineage):
            return True
    return False


def _ancestor_lineage(org, position_id: int, _max_depth: int = 20) -> list[tuple[str, str]]:
    """(title, classification) for the given position and every ancestor up to the org root."""
    lineage: list[tuple[str, str]] = []
    current_id = position_id
    for _ in range(_max_depth):
        if current_id is None:
            break
        position = org.get_position(current_id)
        if position is None:
            break
        lineage.append((position.title, position.classification))
        current_id = position.parent_position_id
    return lineage
