"""Validation helpers for the resource request service."""

from __future__ import annotations

from typing import Dict, Iterable, Optional

from ..models.enums import (
    ALLOWED_STATUS_TRANSITIONS,
    ApprovalAction,
    FulfillmentStatus,
    ItemKind,
    Priority,
    RequestStatus,
    REOPEN_TARGET,
    SUBMISSION_STATUSES,
    TERMINAL_STATUSES,
)


class ValidationError(RuntimeError):
    """Raised when validation fails."""


def _normalise(value: object) -> str:
    if isinstance(value, str):
        return value.upper()
    if isinstance(value, (Priority, RequestStatus, ItemKind, FulfillmentStatus, ApprovalAction)):
        return value.value
    raise ValidationError(f"Unsupported enum value: {value}")


def validate_priority(value: object) -> Priority:
    try:
        return Priority(_normalise(value))
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValidationError(str(exc)) from exc


def validate_status(value: object) -> RequestStatus:
    try:
        return RequestStatus(_normalise(value))
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValidationError(str(exc)) from exc


def validate_item_kind(value: object) -> ItemKind:
    try:
        return ItemKind(_normalise(value))
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValidationError(str(exc)) from exc


def validate_fulfillment_status(value: object) -> FulfillmentStatus:
    try:
        return FulfillmentStatus(_normalise(value))
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc


def validate_status_transition(current: RequestStatus, target: RequestStatus) -> None:
    if current == target:
        return

    allowed = ALLOWED_STATUS_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ValidationError(f"Illegal status transition: {current.value} -> {target.value}")


def ensure_edit_allowed(current_status: RequestStatus) -> None:
    if current_status in TERMINAL_STATUSES:
        raise ValidationError(f"Request in terminal status {current_status.value} cannot be modified")


def ensure_post_submission_edit_allowed(current_status: RequestStatus, fields: Iterable[str]) -> None:
    if current_status in SUBMISSION_STATUSES - {RequestStatus.DRAFT}:
        forbidden = {"title", "requesting_section", "priority"}
        changed = forbidden.intersection(fields)
        if changed:
            raise ValidationError(
                "Cannot modify critical fields after submission: " + ", ".join(sorted(changed))
            )


def normalise_status_for_transition(current: RequestStatus, target: RequestStatus) -> RequestStatus:
    """Return the actual status to write when transitioning.

    Denied/cancelled reopening flows use REVIEWED as the underlying status.
    """

    if target == RequestStatus.REVIEWED and current in REOPEN_TARGET:
        return REOPEN_TARGET[current]
    return target


def validate_approval_action(action: object, note: Optional[str]) -> ApprovalAction:
    try:
        parsed = ApprovalAction(_normalise(action))
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    if parsed == ApprovalAction.DENY and not note:
        raise ValidationError("Denial requires a note for audit trail compliance")
    return parsed
