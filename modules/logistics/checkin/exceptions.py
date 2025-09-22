"""Custom exceptions for the Logistics Check-In module."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .models import CheckInRecord


class CheckInError(RuntimeError):
    """Base exception for check-in operations."""


class PermissionDenied(CheckInError):
    """Raised when the active user lacks the required permission."""


class NoShowGuardError(CheckInError):
    """Raised when attempting to mark a record as ``NoShow`` after activity."""


@dataclass(slots=True)
class ConflictDetails:
    """Represents a conflict between the local payload and remote record."""

    mine: Dict[str, Any]
    latest: Dict[str, Any]


class ConflictError(CheckInError):
    """Raised when ``updated_at`` guards detect a conflicting write."""

    def __init__(self, details: ConflictDetails) -> None:
        super().__init__("Check-in record is out of date")
        self.details = details


class OfflineQueued(CheckInError):
    """Raised when an operation is queued due to offline mode."""

    def __init__(self, record: "CheckInRecord", pending: int) -> None:
        super().__init__("Operation queued while offline")
        self.record = record
        self.pending = pending


__all__ = [
    "CheckInError",
    "PermissionDenied",
    "NoShowGuardError",
    "ConflictDetails",
    "ConflictError",
    "OfflineQueued",
]
