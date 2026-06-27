"""
Data models for Work Assignments and all related sub-records.

These are plain Python dataclasses used for passing data between the
repository and the UI. The repository (`data/work_assignment_repository.py`)
is API-backed via `utils.api_client`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Allowed status values — kept here so the UI and the repository share them.
# ---------------------------------------------------------------------------

PLANNING_STATUS_VALUES = [
    "Draft",
    "Under Review",
    "Approved",
    "Ready for IAP",
    "Assigned to Operations",
    "In Progress",
    "Complete",
    "Cancelled",
    "Archived",
]

SAFETY_STATUS_VALUES = [
    "Unchecked",
    "Needs Review",
    "Hazards Identified",
    "Mitigations Complete",
    "Safety Approved",
    "Safety Concern",
]

RESOURCE_STATUS_VALUES = [
    "Unreviewed",
    "Needs Identified",
    "Partially Filled",
    "Filled",
    "Overfilled",
    "Gap Exists",
    "Logistics Requested",
]

ASSIGNMENT_KIND_VALUES = [
    "Ground",
    "Air",
    "Logistics",
    "Communications",
    "Medical",
    "Safety",
    "Planning",
    "Staging",
    "Other",
]

PRIORITY_VALUES = ["Low", "Normal", "High", "Urgent"]

OUTPUT_TYPE_VALUES = ["ICS 204", "ICS 215", "ICS 215A", "Briefing Sheet"]

OUTPUT_STATUS_VALUES = [
    "Not Started",
    "In Progress",
    "Needs Review",
    "Ready",
    "Generated",
]

LOG_ENTRY_TYPES = ["Note", "Status Change", "Resource Change", "Hazard Change", "Task Link", "System"]


# ---------------------------------------------------------------------------
# Main work assignment record
# ---------------------------------------------------------------------------

@dataclass
class WorkAssignment:
    """Represents one planning-level Work Assignment."""

    id: int | None = None
    assignment_number: str = ""
    assignment_name: str = ""
    objective_id: str | None = None
    operational_period_id: int | None = None
    branch: str = ""
    division_group: str = ""
    location: str = ""
    location_facility_id: str = ""
    assignment_kind: str = "Ground"
    priority: str = "Normal"
    planning_status: str = "Draft"
    safety_status: str = "Unchecked"
    resource_status: str = "Unreviewed"
    description: str = ""
    tactics_summary: str = ""
    special_instructions: str = ""
    prepared_by: int | None = None
    approved_by: int | None = None
    created_at: str = ""
    updated_at: str = ""
    created_by: int | None = None
    updated_by: int | None = None
    is_archived: int = 0
    notes: str = ""

    def to_db_dict(self) -> dict[str, Any]:
        return {
            "assignment_number": self.assignment_number,
            "assignment_name": self.assignment_name,
            "objective_id": self.objective_id,
            "operational_period_id": self.operational_period_id,
            "branch": self.branch,
            "division_group": self.division_group,
            "location": self.location,
            "location_facility_id": self.location_facility_id,
            "assignment_kind": self.assignment_kind,
            "priority": self.priority,
            "planning_status": self.planning_status,
            "safety_status": self.safety_status,
            "resource_status": self.resource_status,
            "description": self.description,
            "tactics_summary": self.tactics_summary,
            "special_instructions": self.special_instructions,
            "prepared_by": self.prepared_by,
            "approved_by": self.approved_by,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
            "is_archived": self.is_archived,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Resource requirement line
# ---------------------------------------------------------------------------

@dataclass
class WorkAssignmentResourceRequirement:
    """One resource need line on a Work Assignment (ICS 215 style)."""

    id: int | None = None
    work_assignment_id: int = 0
    resource_type_id: int | None = None     # NULL when free-typed
    resource_type_text: str = ""            # always required
    capability_id: int | None = None
    capability_text: str = ""
    quantity_required: int = 1
    quantity_assigned: int = 0
    quantity_available: int = 0
    quantity_gap: int = 0
    unit: str = ""
    priority: str = "Normal"
    source_note: str = ""
    logistics_request_id: int | None = None
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""


# ---------------------------------------------------------------------------
# Actual resource linked to a requirement
# ---------------------------------------------------------------------------

@dataclass
class WorkAssignmentResourceAssignment:
    """An actual resource (personnel / team / vehicle / etc.) linked to a need."""

    id: int | None = None
    work_assignment_resource_id: int = 0
    resource_kind: str = ""     # personnel, team, vehicle, equipment, etc.
    resource_id: str = ""
    display_name: str = ""
    status: str = "Planned"
    assigned_at: str = ""
    released_at: str = ""
    notes: str = ""


# ---------------------------------------------------------------------------
# Hazard line
# ---------------------------------------------------------------------------

@dataclass
class WorkAssignmentHazard:
    """A hazard identified for a Work Assignment (ICS 215A style)."""

    id: int | None = None
    work_assignment_id: int = 0
    hazard_type_id: int | None = None       # NULL when free-typed
    hazard_type_text: str = ""              # always required
    category: str = ""
    risk_level: str = "Unknown"
    likelihood: str = "Unknown"
    severity: str = "Unknown"
    control_measure: str = ""
    mitigation_text: str = ""
    ppe_text: str = ""
    safety_message: str = ""
    source: str = ""
    is_resolved: int = 0
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""


# ---------------------------------------------------------------------------
# Communications channel
# ---------------------------------------------------------------------------

@dataclass
class WorkAssignmentComms:
    """Assignment-specific communications channel entry."""

    id: int | None = None
    work_assignment_id: int = 0
    channel_id: str | None = None
    channel_name: str = ""
    function: str = ""
    zone: str = ""
    channel_number: str = ""
    rx_freq: str = ""
    rx_tone: str = ""
    tx_freq: str = ""
    tx_tone: str = ""
    mode: str = ""
    remarks: str = ""
    is_primary: int = 0
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""


# ---------------------------------------------------------------------------
# Task link
# ---------------------------------------------------------------------------

@dataclass
class WorkAssignmentTaskLink:
    """Links a planning Work Assignment to an existing Operations task."""

    id: int | None = None
    work_assignment_id: int = 0
    task_id: int = 0
    link_type: str = "Generated"    # Generated | Linked Existing | Reference Only
    created_at: str = ""
    created_by: int | None = None
    notes: str = ""


# ---------------------------------------------------------------------------
# Planning log entry
# ---------------------------------------------------------------------------

@dataclass
class WorkAssignmentLogEntry:
    """A planning log or audit entry for a Work Assignment."""

    id: int | None = None
    work_assignment_id: int = 0
    timestamp: str = ""
    entered_by: int | None = None
    entry_type: str = "Note"
    entry_text: str = ""
    critical: int = 0


# ---------------------------------------------------------------------------
# Output status tracker
# ---------------------------------------------------------------------------

@dataclass
class WorkAssignmentOutputStatus:
    """Tracks readiness of a planning output (ICS 215, 215A, 204, etc.)."""

    id: int | None = None
    work_assignment_id: int = 0
    output_type: str = ""           # ICS 204 | ICS 215 | ICS 215A | Briefing Sheet
    status: str = "Not Started"
    generated_file_path: str = ""
    generated_at: str = ""
    generated_by: int | None = None
    notes: str = ""


# ---------------------------------------------------------------------------
# Summary view models (not persisted — computed on demand)
# ---------------------------------------------------------------------------

@dataclass
class ResourceGapSummary:
    """Rolled-up resource gap view for one Work Assignment."""

    work_assignment_id: int = 0
    total_required: int = 0
    total_assigned: int = 0
    total_available: int = 0
    total_gap: int = 0
    has_gap: bool = False
    lines: list[WorkAssignmentResourceRequirement] = field(default_factory=list)


@dataclass
class HazardSummary:
    """Rolled-up hazard view for one Work Assignment."""

    work_assignment_id: int = 0
    total_hazards: int = 0
    unresolved: int = 0
    has_critical: bool = False
    lines: list[WorkAssignmentHazard] = field(default_factory=list)
