"""
Data models for Work Assignments and all related sub-records.

These are plain Python dataclasses used for passing data between the
repository and the UI.  They are NOT SQLAlchemy ORM models — the
repository uses raw sqlite3 so we can use CREATE TABLE IF NOT EXISTS
and additive migrations without touching ORM metadata.
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
# Helper to convert a sqlite3.Row (or dict) to a plain dict safely.
# ---------------------------------------------------------------------------
def _row_to_dict(row: Any) -> dict[str, Any]:
    if hasattr(row, "keys"):
        return dict(row)
    return {}


# ---------------------------------------------------------------------------
# Main work assignment record
# ---------------------------------------------------------------------------

@dataclass
class WorkAssignment:
    """Represents one planning-level Work Assignment."""

    id: int | None = None
    assignment_number: str = ""
    assignment_name: str = ""
    objective_id: int | None = None
    operational_period_id: int | None = None
    branch: str = ""
    division_group: str = ""
    location: str = ""
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

    @classmethod
    def from_row(cls, row: Any) -> "WorkAssignment":
        d = _row_to_dict(row)
        return cls(
            id=d.get("id"),
            assignment_number=d.get("assignment_number") or "",
            assignment_name=d.get("assignment_name") or "",
            objective_id=d.get("objective_id"),
            operational_period_id=d.get("operational_period_id"),
            branch=d.get("branch") or "",
            division_group=d.get("division_group") or "",
            location=d.get("location") or "",
            assignment_kind=d.get("assignment_kind") or "Ground",
            priority=d.get("priority") or "Normal",
            planning_status=d.get("planning_status") or "Draft",
            safety_status=d.get("safety_status") or "Unchecked",
            resource_status=d.get("resource_status") or "Unreviewed",
            description=d.get("description") or "",
            tactics_summary=d.get("tactics_summary") or "",
            special_instructions=d.get("special_instructions") or "",
            prepared_by=d.get("prepared_by"),
            approved_by=d.get("approved_by"),
            created_at=d.get("created_at") or "",
            updated_at=d.get("updated_at") or "",
            created_by=d.get("created_by"),
            updated_by=d.get("updated_by"),
            is_archived=int(d.get("is_archived") or 0),
            notes=d.get("notes") or "",
        )

    def to_db_dict(self) -> dict[str, Any]:
        return {
            "assignment_number": self.assignment_number,
            "assignment_name": self.assignment_name,
            "objective_id": self.objective_id,
            "operational_period_id": self.operational_period_id,
            "branch": self.branch,
            "division_group": self.division_group,
            "location": self.location,
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

    @classmethod
    def from_row(cls, row: Any) -> "WorkAssignmentResourceRequirement":
        d = _row_to_dict(row)
        return cls(
            id=d.get("id"),
            work_assignment_id=d.get("work_assignment_id") or 0,
            resource_type_id=d.get("resource_type_id"),
            resource_type_text=d.get("resource_type_text") or "",
            capability_id=d.get("capability_id"),
            capability_text=d.get("capability_text") or "",
            quantity_required=int(d.get("quantity_required") or 1),
            quantity_assigned=int(d.get("quantity_assigned") or 0),
            quantity_available=int(d.get("quantity_available") or 0),
            quantity_gap=int(d.get("quantity_gap") or 0),
            unit=d.get("unit") or "",
            priority=d.get("priority") or "Normal",
            source_note=d.get("source_note") or "",
            logistics_request_id=d.get("logistics_request_id"),
            notes=d.get("notes") or "",
            created_at=d.get("created_at") or "",
            updated_at=d.get("updated_at") or "",
        )


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

    @classmethod
    def from_row(cls, row: Any) -> "WorkAssignmentResourceAssignment":
        d = _row_to_dict(row)
        return cls(
            id=d.get("id"),
            work_assignment_resource_id=d.get("work_assignment_resource_id") or 0,
            resource_kind=d.get("resource_kind") or "",
            resource_id=str(d.get("resource_id") or ""),
            display_name=d.get("display_name") or "",
            status=d.get("status") or "Planned",
            assigned_at=d.get("assigned_at") or "",
            released_at=d.get("released_at") or "",
            notes=d.get("notes") or "",
        )


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

    @classmethod
    def from_row(cls, row: Any) -> "WorkAssignmentHazard":
        d = _row_to_dict(row)
        return cls(
            id=d.get("id"),
            work_assignment_id=d.get("work_assignment_id") or 0,
            hazard_type_id=d.get("hazard_type_id"),
            hazard_type_text=d.get("hazard_type_text") or "",
            category=d.get("category") or "",
            risk_level=d.get("risk_level") or "Unknown",
            likelihood=d.get("likelihood") or "Unknown",
            severity=d.get("severity") or "Unknown",
            control_measure=d.get("control_measure") or "",
            mitigation_text=d.get("mitigation_text") or "",
            ppe_text=d.get("ppe_text") or "",
            safety_message=d.get("safety_message") or "",
            source=d.get("source") or "",
            is_resolved=int(d.get("is_resolved") or 0),
            notes=d.get("notes") or "",
            created_at=d.get("created_at") or "",
            updated_at=d.get("updated_at") or "",
        )


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

    @classmethod
    def from_row(cls, row: Any) -> "WorkAssignmentComms":
        d = _row_to_dict(row)
        return cls(
            id=d.get("id"),
            work_assignment_id=d.get("work_assignment_id") or 0,
            channel_id=d.get("channel_id"),
            channel_name=d.get("channel_name") or "",
            function=d.get("function") or "",
            zone=d.get("zone") or "",
            channel_number=d.get("channel_number") or "",
            rx_freq=d.get("rx_freq") or "",
            rx_tone=d.get("rx_tone") or "",
            tx_freq=d.get("tx_freq") or "",
            tx_tone=d.get("tx_tone") or "",
            mode=d.get("mode") or "",
            remarks=d.get("remarks") or "",
            is_primary=int(d.get("is_primary") or 0),
            notes=d.get("notes") or "",
            created_at=d.get("created_at") or "",
            updated_at=d.get("updated_at") or "",
        )


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

    @classmethod
    def from_row(cls, row: Any) -> "WorkAssignmentTaskLink":
        d = _row_to_dict(row)
        return cls(
            id=d.get("id"),
            work_assignment_id=d.get("work_assignment_id") or 0,
            task_id=d.get("task_id") or 0,
            link_type=d.get("link_type") or "Generated",
            created_at=d.get("created_at") or "",
            created_by=d.get("created_by"),
            notes=d.get("notes") or "",
        )


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

    @classmethod
    def from_row(cls, row: Any) -> "WorkAssignmentLogEntry":
        d = _row_to_dict(row)
        return cls(
            id=d.get("id"),
            work_assignment_id=d.get("work_assignment_id") or 0,
            timestamp=d.get("timestamp") or "",
            entered_by=d.get("entered_by"),
            entry_type=d.get("entry_type") or "Note",
            entry_text=d.get("entry_text") or "",
            critical=int(d.get("critical") or 0),
        )


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

    @classmethod
    def from_row(cls, row: Any) -> "WorkAssignmentOutputStatus":
        d = _row_to_dict(row)
        return cls(
            id=d.get("id"),
            work_assignment_id=d.get("work_assignment_id") or 0,
            output_type=d.get("output_type") or "",
            status=d.get("status") or "Not Started",
            generated_file_path=d.get("generated_file_path") or "",
            generated_at=d.get("generated_at") or "",
            generated_by=d.get("generated_by"),
            notes=d.get("notes") or "",
        )


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
