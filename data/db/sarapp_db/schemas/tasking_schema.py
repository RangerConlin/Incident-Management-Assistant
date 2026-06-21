"""Schemas for tasking documents (tasks, task_narrative, task_team_assignments)."""

from __future__ import annotations

from typing import List, Optional

from pydantic import Field

from sarapp_db.schemas.common import TimestampedDocument


class TaskDocument(TimestampedDocument):
    """A field task assigned during an incident. task_number is unique per incident."""

    incident_id: str
    task_number: str
    title: str
    description: Optional[str] = None
    status: str = "pending"   # pending | active | completed | cancelled
    priority: str = "normal"  # low | normal | high | urgent
    operational_period_id: Optional[str] = None
    linked_objective_ids: List[str] = Field(default_factory=list)
    assigned_team_ids: List[str] = Field(default_factory=list)
    assigned_personnel_ids: List[str] = Field(default_factory=list)
    assigned_vehicle_ids: List[str] = Field(default_factory=list)
    search_area: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    assigned_at: Optional[str] = None
    completed_at: Optional[str] = None
    due_at: Optional[str] = None
    notes: Optional[str] = None


class TaskNarrativeEntry(TimestampedDocument):
    """A single narrative/log entry attached to a task."""

    task_id: str
    incident_id: str
    entry_text: str
    author_user_id: Optional[str] = None
    author_display_name: Optional[str] = None
    critical: bool = False
    entry_type: str = "note"  # note | status_change | location_update | alert


class TaskTeamAssignment(TimestampedDocument):
    """Links a team to a task. primary=True means lead team for the task."""

    task_id: str
    team_id: str
    status: str = "assigned"  # assigned | en_route | on_scene | released
    primary: bool = False
    operational_period_id: Optional[str] = None
    notes: Optional[str] = None
