"""Schema for the shared notification documents (sarapp_incident_<id>.notifications).

This is the program-wide notification store — not owned by any single feature
module. Any part of the app may emit a notification here via
`sarapp_db.services.notification_service.emit_notification`; the Planned
Events Toolkit's schedule triggers are its first caller, not its owner.

`severity`/`category` values are kept identical to the desktop client's
`notifications.models.notification.Notification` Literal sets so a future
desktop-toast bridge needs no translation layer.
"""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field

Severity = Literal["informational", "routine", "priority", "emergency"]
Category = Literal[
    "operations",
    "communications",
    "safety",
    "logistics",
    "planning",
    "administrative",
    "system",
]


class NotificationDocument(BaseModel):
    """Persisted shape of a document in the `notifications` collection."""

    notification_id: int
    incident_id: str
    title: str
    message: str
    severity: Severity = "routine"
    category: Category = "operations"

    # Provenance — links back to whatever produced this notification.
    source_type: str
    source_id: str
    source_label: Optional[str] = None

    # Audience targeting — any combination may be set.
    audience_role: Optional[str] = None
    audience_user_id: Optional[int] = None
    audience_team_id: Optional[int] = None

    requires_acknowledgement: bool = False
    read: bool = False

    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    acknowledged_at: Optional[str] = None
    acknowledged_by: Optional[str] = None
    dismissed_at: Optional[str] = None
    dismissed_by: Optional[str] = None

    delivery: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}
