from __future__ import annotations

"""Data objects for incident organization management.

The incident organization is the source of truth. ICS 203 and ICS 207 are
produced later from these records instead of being stored as form-first data.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


ASSIGNMENT_TYPE_PRIMARY = "primary"
ASSIGNMENT_TYPE_DEPUTY = "deputy"
ASSIGNMENT_TYPE_ASSISTANT = "assistant"
ASSIGNMENT_TYPE_STAFF_ASSISTANT = "staff_assistant"
ASSIGNMENT_TYPE_TRAINEE = "trainee"
ASSIGNMENT_TYPE_RELIEF = "relief"
_LEGACY_ASSIGNMENT_TYPE_ALIASES = {
    "staff assistant": ASSIGNMENT_TYPE_STAFF_ASSISTANT,
}
ACTIVE_ASSIGNMENT_TYPES = {
    ASSIGNMENT_TYPE_PRIMARY,
    ASSIGNMENT_TYPE_DEPUTY,
    ASSIGNMENT_TYPE_ASSISTANT,
    ASSIGNMENT_TYPE_STAFF_ASSISTANT,
    ASSIGNMENT_TYPE_TRAINEE,
    ASSIGNMENT_TYPE_RELIEF,
}
POSITION_STATUSES = {"active", "inactive"}


def normalize_assignment_type(value: object) -> str:
    """Normalize stored or user-selected assignment types.

    Accept a few loose text variants while preserving distinct ICS support
    roles like ``assistant`` and ``staff_assistant``.
    """

    assignment_type = str(value or ASSIGNMENT_TYPE_PRIMARY).strip().lower()
    if not assignment_type:
        return ASSIGNMENT_TYPE_PRIMARY
    assignment_type = _LEGACY_ASSIGNMENT_TYPE_ALIASES.get(assignment_type, assignment_type)
    return (
        assignment_type
        if assignment_type in ACTIVE_ASSIGNMENT_TYPES
        else ASSIGNMENT_TYPE_PRIMARY
    )


@dataclass(slots=True)
class OrganizationPosition:
    """A position or organizational node in the incident structure."""

    id: Optional[int]
    incident_id: str
    title: str
    classification: str
    parent_position_id: Optional[int] = None
    operational_period: Optional[str] = None
    required_qualifications: list[str] = field(default_factory=list)
    is_critical: bool = False
    is_custom: bool = False
    is_air_ops: bool = False
    status: str = "active"
    sort_order: int = 0
    notes: Optional[str] = None


@dataclass(slots=True)
class OrganizationTemplate:
    """Reusable organization structure that can be loaded into an incident."""

    id: Optional[int]
    incident_id: Optional[str]
    name: str
    description: Optional[str]
    payload: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class PositionAssignment:
    """Personnel assignment to an organization position."""

    id: Optional[int]
    incident_id: str
    position_id: int
    personnel_id: Optional[str]
    display_name: str
    assignment_type: str = ASSIGNMENT_TYPE_PRIMARY
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    operational_period: Optional[str] = None
    assigned_by: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass(slots=True)
class AssignmentHistoryEntry:
    """Audit-style assignment history record."""

    id: Optional[int]
    incident_id: str
    assignment_id: Optional[int]
    position_id: int
    personnel_id: Optional[str]
    display_name: str
    assignment_type: str
    action: str
    effective_time: Optional[str]
    operational_period: Optional[str]
    changed_by: Optional[str]
    notes: Optional[str] = None


@dataclass(slots=True)
class PositionRequirement:
    """Qualification or staffing requirement attached to a position."""

    id: Optional[int]
    incident_id: str
    position_id: int
    qualification: str
    is_required: bool = True
    notes: Optional[str] = None


@dataclass(slots=True)
class OrganizationWarning:
    """Non-blocking warning shown to planners and staffing users."""

    level: str
    code: str
    message: str
    position_id: Optional[int] = None


@dataclass(slots=True)
class PositionStatusSummary:
    """Calculated status for a position."""

    position_id: int
    staffing_status: str
    warnings: list[OrganizationWarning] = field(default_factory=list)


@dataclass(slots=True)
class GeneratedFormSnapshot:
    """Metadata for generated ICS outputs derived from the organization."""

    id: Optional[int]
    incident_id: str
    form_type: str
    generated_at: str
    operational_period: Optional[str]
    source_version: Optional[str]
    payload: dict[str, Any]
