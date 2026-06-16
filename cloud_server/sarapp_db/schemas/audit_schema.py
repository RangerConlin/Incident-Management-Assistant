"""Schema for audit log documents (sarapp_incident_<id>.audit_logs).

Audit records are append-only — never updated or deleted.
"""

from __future__ import annotations

from typing import Any, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def _new_id() -> str:
    return str(uuid4())


class FieldChange(BaseModel):
    """Describes a single field that changed within an update action."""

    field: str
    old: Optional[Any] = None
    new: Optional[Any] = None


class AuditLogDocument(BaseModel):
    """
    Immutable audit record. Written by audit.write_audit(), never modified after.
    """

    id: str = Field(default_factory=_new_id, alias="_id")
    incident_id: str
    entity_type: str    # e.g. "task", "team", "personnel"
    entity_id: str
    action: str         # "created" | "updated" | "deleted" | "restored"
    changed_by: str
    timestamp: str
    field_changes: List[FieldChange] = Field(default_factory=list)
    source_module: Optional[str] = None

    model_config = {"populate_by_name": True}
