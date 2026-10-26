"""Program-wide notifications router (MongoDB-backed).

Shared infrastructure, not owned by any single feature module — see
docs/archive/design-documents/Instructions/planned_events_phase0_audit.md. The Planned
Events Toolkit's schedule triggers are the first caller of
`emit_notification` (via `sarapp_db.services.trigger_engine`), not the owner
of this router.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from sarapp_db.services import notification_service

router = APIRouter()


class NotificationEmitRequest(BaseModel):
    title: str
    message: str
    source_type: str
    source_id: str
    severity: str = "routine"
    category: str = "operations"
    source_label: Optional[str] = None
    audience_role: Optional[str] = None
    audience_user_id: Optional[int] = None
    audience_team_id: Optional[int] = None
    requires_acknowledgement: bool = False


class RecipientActionRequest(BaseModel):
    person_record: Optional[int] = None


def _actor_person_record(authorization: Optional[str], explicit: Optional[int]) -> int:
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(401, "Invalid authorization header")
        from sarapp_db.api.routers.auth_sessions import decode_access_token

        claims = decode_access_token(token)
        value = claims.get("person_record")
        if value is None:
            raise HTTPException(403, "Signed-in account is not linked to personnel")
        if explicit is not None and int(value) != explicit:
            raise HTTPException(403, "Notification identity does not match the signed-in user")
        return int(value)
    if explicit is None:
        raise HTTPException(401, "A signed-in person is required")
    return int(explicit)


def _out(doc: Dict[str, Any]) -> Dict[str, Any]:
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


@router.post("/incidents/{incident_id}/notifications")
def emit_notification(incident_id: str, body: NotificationEmitRequest) -> Dict[str, Any]:
    doc = notification_service.emit_notification(
        incident_id,
        title=body.title,
        message=body.message,
        severity=body.severity,
        category=body.category,
        source_type=body.source_type,
        source_id=body.source_id,
        source_label=body.source_label,
        audience_role=body.audience_role,
        audience_user_id=body.audience_user_id,
        audience_team_id=body.audience_team_id,
        requires_acknowledgement=body.requires_acknowledgement,
    )
    return _out(doc)


@router.get("/incidents/{incident_id}/notifications")
def list_notifications(
    incident_id: str,
    audience_role: str = "",
    audience_user_id: Optional[int] = None,
    person_record: Optional[int] = None,
    unread_only: bool = False,
    source_type: str = "",
    source_id: str = "",
    authorization: Optional[str] = Header(None),
) -> List[Dict[str, Any]]:
    if authorization:
        person_record = _actor_person_record(authorization, person_record)
    docs = notification_service.list_notifications(
        incident_id,
        audience_role=audience_role or None,
        audience_user_id=audience_user_id,
        person_record=person_record,
        unread_only=unread_only,
        source_type=source_type or None,
        source_id=source_id or None,
    )
    return [_out(doc) for doc in docs]


@router.post("/incidents/{incident_id}/notifications/{notification_id}/acknowledge")
def acknowledge_notification(
    incident_id: str,
    notification_id: int,
    body: RecipientActionRequest,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    actor = _actor_person_record(authorization, body.person_record)
    doc = notification_service.acknowledge_notification(
        incident_id, notification_id, person_record=actor
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return _out(doc)


@router.post("/incidents/{incident_id}/notifications/{notification_id}/dismiss")
def dismiss_notification(
    incident_id: str,
    notification_id: int,
    body: RecipientActionRequest,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    actor = _actor_person_record(authorization, body.person_record)
    doc = notification_service.dismiss_notification(
        incident_id, notification_id, person_record=actor
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return _out(doc)
