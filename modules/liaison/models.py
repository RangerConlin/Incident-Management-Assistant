"""Dataclasses and controlled vocabularies for the Liaison module."""
from __future__ import annotations

from dataclasses import dataclass

AGENCY_STATUSES = [
    "Not Contacted",
    "Contacted",
    "Awaiting Response",
    "Standby",
    "Supporting",
    "Active",
    "Demobilizing",
    "Released",
    "Unavailable",
]

FEEDBACK_TYPES = [
    "Positive Feedback",
    "Concern",
    "Deficiency",
    "Change Request",
    "Additional Requirement",
    "Approval",
    "Rejection",
    "Closure Confirmation",
    "Complaint",
    "Other",
]

FEEDBACK_STATUSES = [
    "Open",
    "Under Review",
    "Routed",
    "Action Required",
    "Resolved",
    "Closed",
    "Cancelled",
]

VALIDATION_STATUSES = [
    "Not Reviewed",
    "Pending Feedback",
    "Validated",
    "Rejected",
    "Requires Revision",
]

INTERACTION_TYPES = [
    "Meeting",
    "Call",
    "Email",
    "Radio Contact",
    "Briefing",
    "Site Visit",
    "Video Conference",
    "Other",
]

PRIORITIES = ["Low", "Medium", "High", "Critical"]
FOLLOWUP_STATUSES = ["Open", "In Progress", "Complete", "Cancelled"]
REQUEST_STATUSES = ["Open", "In Progress", "Filled", "Declined", "Cancelled", "Closed"]
OFFER_STATUSES = ["Offered", "Under Review", "Accepted", "Declined", "Released"]


@dataclass(slots=True)
class Agency:
    id: int | None = None
    incident_id: str | None = None
    name: str = ""
    agency_type: str = ""
    jurisdiction: str = ""
    current_status: str = "Not Contacted"
    assigned_liaison: str = ""
    last_contact: str = ""
    next_contact_due: str = ""
    priority: str = "Medium"
    notes: str = ""


@dataclass(slots=True)
class FeedbackItem:
    id: int | None = None
    incident_id: str | None = None
    agency_id: int | None = None
    contact_id: int | None = None
    feedback_type: str = "Concern"
    priority: str = "Medium"
    summary: str = ""
    requested_action: str = ""
    assigned_to: str = ""
    assigned_section: str = ""
    status: str = "Open"
    interaction_id: int | None = None
    objective_id: int | None = None
    strategy_id: int | None = None
    task_id: int | None = None
    resource_request_id: int | None = None
    validation_status: str = "Pending Feedback"
    followup_due: str = ""
    entered_by: str = ""
    entered_ts: str = ""
    resolved_by: str = ""
    resolved_ts: str = ""
    resolution_notes: str = ""


__all__ = [
    "AGENCY_STATUSES",
    "FEEDBACK_TYPES",
    "FEEDBACK_STATUSES",
    "VALIDATION_STATUSES",
    "INTERACTION_TYPES",
    "PRIORITIES",
    "FOLLOWUP_STATUSES",
    "REQUEST_STATUSES",
    "OFFER_STATUSES",
    "Agency",
    "FeedbackItem",
]
