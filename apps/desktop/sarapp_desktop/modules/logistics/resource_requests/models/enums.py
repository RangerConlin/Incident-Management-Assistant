"""Enumerations used throughout the resource request module."""

from __future__ import annotations

from enum import Enum
from typing import Set


class _StrEnum(str, Enum):
    """Enum subclass that compares/serialises as its value."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)

    @classmethod
    def values(cls) -> Set[str]:
        return {member.value for member in cls}

    @classmethod
    def has_value(cls, value: str) -> bool:
        return value in cls.values()


class Priority(_StrEnum):
    IMMEDIATE = "IMMEDIATE"
    HIGH = "HIGH"
    ROUTINE = "ROUTINE"


class RequestStatus(_StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    REVIEWED = "REVIEWED"
    APPROVED = "APPROVED"
    ASSIGNED = "ASSIGNED"
    INTRANSIT = "INTRANSIT"
    DELIVERED = "DELIVERED"
    PARTIAL = "PARTIAL"
    DENIED = "DENIED"
    CANCELLED = "CANCELLED"
    CLOSED = "CLOSED"


class ItemKind(_StrEnum):
    PERSONNEL = "PERSONNEL"
    TEAM = "TEAM"
    EQUIPMENT = "EQUIPMENT"
    VEHICLE = "VEHICLE"
    AIRCRAFT = "AIRCRAFT"
    SUPPLY = "SUPPLY"
    SERVICE = "SERVICE"
    COMMUNICATIONS = "COMMUNICATIONS"


class ApprovalAction(_StrEnum):
    SUBMIT = "SUBMIT"
    REVIEW = "REVIEW"
    APPROVE = "APPROVE"
    DENY = "DENY"
    CANCEL = "CANCEL"
    REOPEN = "REOPEN"
    # Finance/Admin's cost sign-off — conditional (only requests with a cost
    # impact need one) and independent of the status chain below, unlike
    # every other action here.
    FINANCE_APPROVE = "FINANCE_APPROVE"
    FINANCE_DENY = "FINANCE_DENY"


class ApprovalSection(_StrEnum):
    """ICS-213RR responsibility tier an approval belongs to — mirrors
    server/sarapp_db/sarapp_db/api/routers/logistics_resource_requests.py
    and apps/web/src/modules/logistics/model.ts's SECTIONS."""

    REQUESTING = "requesting"
    LOGISTICS = "logistics"
    FINANCE = "finance"


class FulfillmentStatus(_StrEnum):
    SOURCING = "SOURCING"
    ASSIGNED = "ASSIGNED"
    INTRANSIT = "INTRANSIT"
    DELIVERED = "DELIVERED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


ALLOWED_STATUS_TRANSITIONS = {
    RequestStatus.DRAFT: {RequestStatus.DRAFT, RequestStatus.SUBMITTED, RequestStatus.CANCELLED},
    RequestStatus.SUBMITTED: {
        RequestStatus.REVIEWED,
        RequestStatus.APPROVED,
        RequestStatus.DENIED,
        RequestStatus.CANCELLED,
    },
    RequestStatus.REVIEWED: {RequestStatus.APPROVED, RequestStatus.DENIED, RequestStatus.CANCELLED},
    RequestStatus.APPROVED: {RequestStatus.ASSIGNED, RequestStatus.DENIED, RequestStatus.CANCELLED},
    RequestStatus.ASSIGNED: {RequestStatus.INTRANSIT, RequestStatus.CANCELLED},
    RequestStatus.INTRANSIT: {RequestStatus.DELIVERED, RequestStatus.PARTIAL, RequestStatus.CANCELLED},
    RequestStatus.DELIVERED: {RequestStatus.CLOSED, RequestStatus.PARTIAL},
    RequestStatus.PARTIAL: {RequestStatus.CLOSED, RequestStatus.ASSIGNED},
    RequestStatus.DENIED: {RequestStatus.REVIEWED},
    RequestStatus.CANCELLED: {RequestStatus.REVIEWED},
    RequestStatus.CLOSED: set(),
}

# When reopening we treat the transition as going back to REVIEWED
REOPEN_TARGET = {
    RequestStatus.DENIED: RequestStatus.REVIEWED,
    RequestStatus.CANCELLED: RequestStatus.REVIEWED,
}

SUBMISSION_STATUSES = {
    RequestStatus.SUBMITTED,
    RequestStatus.REVIEWED,
    RequestStatus.APPROVED,
    RequestStatus.ASSIGNED,
    RequestStatus.INTRANSIT,
    RequestStatus.DELIVERED,
    RequestStatus.PARTIAL,
    RequestStatus.CLOSED,
    RequestStatus.DENIED,
    RequestStatus.CANCELLED,
}

TERMINAL_STATUSES = {
    RequestStatus.CLOSED,
    RequestStatus.DENIED,
    RequestStatus.CANCELLED,
}

# Which RequestStatus an approval action moves the request to. Finance
# actions are deliberately absent — they never change `status`.
ACTION_STATUS_MAP = {
    ApprovalAction.SUBMIT: RequestStatus.SUBMITTED,
    ApprovalAction.REVIEW: RequestStatus.REVIEWED,
    ApprovalAction.APPROVE: RequestStatus.APPROVED,
    ApprovalAction.DENY: RequestStatus.DENIED,
    ApprovalAction.CANCEL: RequestStatus.CANCELLED,
    ApprovalAction.REOPEN: RequestStatus.REVIEWED,
}

FINANCE_ACTIONS = {ApprovalAction.FINANCE_APPROVE, ApprovalAction.FINANCE_DENY}

# Default responsibility tier per action, used when the caller doesn't pass
# an explicit `section` — same defaults the server applies.
ACTION_SECTION_MAP = {
    ApprovalAction.SUBMIT: ApprovalSection.REQUESTING,
    ApprovalAction.REVIEW: ApprovalSection.LOGISTICS,
    ApprovalAction.APPROVE: ApprovalSection.LOGISTICS,
    ApprovalAction.DENY: ApprovalSection.LOGISTICS,
    ApprovalAction.CANCEL: ApprovalSection.REQUESTING,
    ApprovalAction.REOPEN: ApprovalSection.REQUESTING,
    ApprovalAction.FINANCE_APPROVE: ApprovalSection.FINANCE,
    ApprovalAction.FINANCE_DENY: ApprovalSection.FINANCE,
}

# Which actions a still-pending row offers per section — Requesting can
# still Cancel while Logistics can still Review/Approve/Deny; both may show
# a pending row for the same request at once.
SECTION_PENDING_ACTIONS = {
    ApprovalSection.REQUESTING: [ApprovalAction.CANCEL, ApprovalAction.REOPEN],
    ApprovalSection.LOGISTICS: [ApprovalAction.REVIEW, ApprovalAction.APPROVE, ApprovalAction.DENY],
    ApprovalSection.FINANCE: [ApprovalAction.FINANCE_APPROVE, ApprovalAction.FINANCE_DENY],
}
