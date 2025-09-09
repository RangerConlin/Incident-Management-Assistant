from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AuditLog:
    """Simple audit trail entry for an objective."""

    id: int
    objective_id: int
    timestamp: str
    user_id: int
    action: str
    note: str | None = None


@dataclass
class ObjectiveComment:
    """Threaded comment on an objective."""

    id: int
    objective_id: int
    user_id: int
    timestamp: str
    text: str
    parent_id: Optional[int] = None


@dataclass
class Objective:
    """Incident objective stored in the mission database."""

    id: int
    mission_id: int
    description: str
    status: str
    priority: str
    created_by: int
    created_at: str
    assigned_section: Optional[str] = None
    customer: Optional[str] = None
    due_time: Optional[str] = None
    closed_at: Optional[str] = None

    comments: List[ObjectiveComment] = field(default_factory=list)
    logs: List[AuditLog] = field(default_factory=list)
