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


class FulfillmentStatus(_StrEnum):
    SOURCING = "SOURCING"
    ASSIGNED = "ASSIGNED"
    INTRANSIT = "INTRANSIT"
    DELIVERED = "DELIVERED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


ALLOWED_STATUS_TRANSITIONS = {
    RequestStatus.DRAFT: {RequestStatus.DRAFT, RequestStatus.SUBMITTED, RequestStatus.CANCELLED},
    RequestStatus.SUBMITTED: {RequestStatus.REVIEWED, RequestStatus.DENIED, RequestStatus.CANCELLED},
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
