"""Service layer for the Logistics Check-In window."""
from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

from utils.state import AppState

from . import repository
from .exceptions import (
    CheckInError,
    ConflictDetails,
    ConflictError,
    NoShowGuardError,
    OfflineQueued,
    PermissionDenied,
)
from .models import (
    CIStatus,
    CheckInRecord,
    CheckInUpsert,
    HistoryItem,
    Location,
    PersonnelIdentity,
    PersonnelStatus,
    QueueItem,
    RosterFilters,
    RosterRow,
    UIFlags,
)

_SHIFT_RE = re.compile(r"^[0-2][0-9][0-5][0-9]$")
_DATA_DIR = Path(os.environ.get("CHECKIN_DATA_DIR", "data"))
_QUEUE_PATH = Path(os.environ.get("CHECKIN_QUEUE_PATH", _DATA_DIR / "offline_queue" / "checkin_queue.json"))


def _now() -> datetime:
    return datetime.now().astimezone()


# ---------------------------------------------------------------------------
# Rule engine
# ---------------------------------------------------------------------------

def apply_rules(record: CheckInRecord, prior: Optional[CheckInRecord] = None) -> CheckInRecord:
    """Apply deterministic personnel status mapping rules."""
    record.ui_flags = UIFlags()
    if record.team_id in {"", "—"}:
        record.team_id = None
    if record.location is not Location.OTHER:
        record.location_other = None
    if record.ci_status is CIStatus.NO_SHOW:
        record.personnel_status = PersonnelStatus.UNAVAILABLE
        record.ui_flags.hidden_by_default = True
    elif record.ci_status is CIStatus.DEMOBILIZED:
        record.personnel_status = PersonnelStatus.DEMOBILIZED
        record.ui_flags.grayed = True
    elif record.ci_status is CIStatus.CHECKED_IN and not record.team_id:
        record.personnel_status = PersonnelStatus.AVAILABLE
    # Legacy normalization handled by CIStatus.normalize earlier
    return record


# ---------------------------------------------------------------------------
# Queue store
# ---------------------------------------------------------------------------


class QueueStore:
    """Persistence helper for offline operations."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.items: List[QueueItem] = repository.load_queue_items(str(self.path))

    def enqueue(self, item: QueueItem) -> None:
        self.items.append(item)
        repository.save_queue_items(str(self.path), self.items)

    def replace(self, items: Iterable[QueueItem]) -> None:
        self.items = list(items)
        repository.save_queue_items(str(self.path), self.items)

    def flush(self, handler: Callable[[QueueItem], bool]) -> None:
        if not self.items:
            return
        remaining: List[QueueItem] = []
        for item in list(self.items):
            if not handler(item):
                remaining.append(item)
        self.replace(remaining)

    def pending_count(self) -> int:
        return len(self.items)


# ---------------------------------------------------------------------------
# Service implementation
# ---------------------------------------------------------------------------


class CheckInService:
    def __init__(self, queue_store: Optional[QueueStore] = None) -> None:
        self.queue = queue_store or QueueStore(_QUEUE_PATH)
        self.offline = False
        self.last_saved_at: Optional[datetime] = None

    # -- Permission helpers -------------------------------------------------
    @staticmethod
    def _active_user_role() -> Optional[str]:
        return AppState.get_active_user_role()

    @staticmethod
    def _active_user_id() -> Optional[str]:
        return AppState.get_active_user_id()

    def _check_override_permission(self, reason: Optional[str]) -> None:
        role = self._active_user_role()
        if role not in {"Logistics", "Command"}:
            raise PermissionDenied("Override Personnel Status requires Logistics or Command role")
        if not reason:
            raise PermissionDenied("Override requires a justification")

    # -- Validation ---------------------------------------------------------
    def _validate_upsert(self, upsert: CheckInUpsert) -> None:
        errors: List[str] = []
        try:
            datetime.fromisoformat(upsert.arrival_time)
        except ValueError:
            errors.append("arrival_time must be ISO 8601")
        if upsert.location is Location.OTHER:
            if not (upsert.location_other or "").strip():
                errors.append("location_other is required when location=Other")
        else:
            upsert.location_other = None
        for label, value in (("shift_start", upsert.shift_start), ("shift_end", upsert.shift_end)):
            if value:
                if not _SHIFT_RE.match(value):
                    errors.append(f"{label} must be HHMM 24-hour")
        if upsert.shift_start and upsert.shift_end:
            start = int(upsert.shift_start[:2]) * 60 + int(upsert.shift_start[2:])
            end = int(upsert.shift_end[:2]) * 60 + int(upsert.shift_end[2:])
            if end <= start:
                errors.append("shift_end must be after shift_start")
        if errors:
            raise ValueError("; ".join(errors))

    # -- History helpers ----------------------------------------------------
    def _log_history(
        self,
        prior: Optional[CheckInRecord],
        record: CheckInRecord,
        actor: str,
        *,
        override_reason: Optional[str] = None,
    ) -> None:
        if prior is None:
            repository.log_history(
                record.person_id,
                actor,
                "CHECKIN_CREATE",
                {
                    "ci_status": record.ci_status.value,
                    "personnel_status": record.personnel_status.value,
                    "arrival_time": record.arrival_time,
                },
            )
            return

        if prior.ci_status != record.ci_status:
            repository.log_history(
                record.person_id,
                actor,
                "CI_STATUS_CHANGE",
                {"from": prior.ci_status.value, "to": record.ci_status.value},
            )
            if record.ci_status is CIStatus.DEMOBILIZED and prior.ci_status is not CIStatus.DEMOBILIZED:
                repository.log_history(
                    record.person_id,
                    actor,
                    "DEMOB",
                    {"status": record.ci_status.value},
                )
        if prior.personnel_status != record.personnel_status:
            repository.log_history(
                record.person_id,
                actor,
                "PERS_STATUS_CHANGE",
                {"from": prior.personnel_status.value, "to": record.personnel_status.value},
            )
        if prior.notes != record.notes:
            repository.log_history(
                record.person_id,
                actor,
                "NOTE",
                {"notes": record.notes or ""},
            )
        if (
            prior.team_id != record.team_id
            or prior.role_on_team != record.role_on_team
            or prior.operational_period != record.operational_period
        ):
            repository.log_history(
                record.person_id,
                actor,
                "ASSIGNMENT_CHANGE",
                {
                    "team_id": record.team_id,
                    "role_on_team": record.role_on_team,
                    "operational_period": record.operational_period,
                },
            )
        if prior.location != record.location or prior.location_other != record.location_other:
            repository.log_history(
                record.person_id,
                actor,
                "LOCATION_CHANGE",
                {
                    "location": record.location.value,
                    "location_other": record.location_other,
                },
            )
        if override_reason:
            repository.log_history(
                record.person_id,
                actor,
                "PERS_STATUS_OVERRIDE",
                {"personnel_status": record.personnel_status.value, "reason": override_reason},
            )

    # -- Core upsert --------------------------------------------------------
    def _execute_upsert(
        self,
        upsert: CheckInUpsert,
        actor: Optional[str],
    ) -> CheckInRecord:
        prior = repository.fetch_checkin(upsert.person_id)
        if upsert.expected_updated_at and prior and prior.updated_at != upsert.expected_updated_at:
            raise ConflictError(
                ConflictDetails(
                    mine=upsert.to_queue_payload(),
                    latest=prior.to_payload(),
                )
            )
        record = upsert.to_record(base=prior)
        record = apply_rules(record, prior)
        if record.ci_status is CIStatus.NO_SHOW and repository.has_activity(record.person_id):
            raise NoShowGuardError("Cannot mark as No Show after activity has been logged")
        record.updated_at = _now().isoformat()
        if prior is None:
            record.created_at = record.updated_at
        else:
            record.created_at = prior.created_at
        repository.save_checkin(record)
        actor_id = actor or self._active_user_id() or "system"
        self._log_history(prior, record, actor_id, override_reason=upsert.override_reason)
        self.last_saved_at = _now()
        record.pending = False
        return record

    def upsert_checkin(self, payload: Dict[str, object] | CheckInUpsert) -> CheckInRecord:
        upsert = payload if isinstance(payload, CheckInUpsert) else CheckInUpsert.from_dict(payload)
        self._validate_upsert(upsert)
        if repository.get_person_identity(upsert.person_id) is None:
            raise ValueError("person_id must exist in master.personnel")
        if upsert.override_personnel_status:
            self._check_override_permission(upsert.override_reason)
        if self.offline:
            prior = repository.fetch_checkin(upsert.person_id)
            record = apply_rules(upsert.to_record(base=prior), prior)
            record.pending = True
            queue_payload = upsert.to_queue_payload()
            queue_payload["__actor"] = self._active_user_id()
            self.queue.enqueue(QueueItem(op="UPSERT_CHECKIN", payload=queue_payload, ts=_now().isoformat()))
            raise OfflineQueued(record, self.queue.pending_count())
        record = self._execute_upsert(upsert, self._active_user_id())
        self.flush_offline_queue()
        return record

    # -- Read queries -------------------------------------------------------
    def get_roster(self, filters: Dict[str, object] | RosterFilters) -> List[RosterRow]:
        filters_obj = filters if isinstance(filters, RosterFilters) else RosterFilters.from_dict(filters)
        return repository.fetch_roster(filters_obj)

    def get_history(self, person_id: str) -> List[HistoryItem]:
        return repository.list_history(person_id)

    def search_personnel(self, term: str) -> List[PersonnelIdentity]:
        return repository.search_personnel(term)

    def get_identity(self, person_id: str) -> Optional[PersonnelIdentity]:
        return repository.get_person_identity(person_id)

    def get_checkin(self, person_id: str) -> Optional[CheckInRecord]:
        return repository.fetch_checkin(person_id)

    def list_roles(self) -> List[str]:
        return repository.get_distinct_roles()

    def list_teams(self) -> List[tuple[str, str]]:
        return repository.get_distinct_teams()

    # -- Offline management -------------------------------------------------
    def set_offline(self, offline: bool) -> None:
        self.offline = offline

    def pending_count(self) -> int:
        return self.queue.pending_count()

    def flush_offline_queue(self) -> None:
        if not self.queue.pending_count():
            return

        def _handler(item: QueueItem) -> bool:
            if item.op != "UPSERT_CHECKIN":
                return False
            payload = dict(item.payload)
            actor = payload.pop("__actor", None)
            upsert = CheckInUpsert.from_dict(payload)
            try:
                identity = repository.get_person_identity(upsert.person_id)
                if identity is None:
                    return False
                self._execute_upsert(upsert, actor)
            except CheckInError:
                return False
            return True

        self.queue.flush(_handler)


# ---------------------------------------------------------------------------
# Module level façade
# ---------------------------------------------------------------------------


_service = CheckInService()


def get_service() -> CheckInService:
    return _service


def getRoster(filters: Dict[str, object]) -> List[RosterRow]:
    return _service.get_roster(filters)


def upsertCheckIn(payload: Dict[str, object] | CheckInUpsert) -> CheckInRecord:
    return _service.upsert_checkin(payload)


def getHistory(person_id: str) -> List[HistoryItem]:
    return _service.get_history(person_id)


def searchPersonnel(term: str) -> List[PersonnelIdentity]:
    return _service.search_personnel(term)


def getIdentity(person_id: str) -> Optional[PersonnelIdentity]:
    return _service.get_identity(person_id)


def getCheckIn(person_id: str) -> Optional[CheckInRecord]:
    return _service.get_checkin(person_id)


def listRoles() -> List[str]:
    return _service.list_roles()


def listTeams() -> List[tuple[str, str]]:
    return _service.list_teams()


def setOffline(offline: bool) -> None:
    _service.set_offline(offline)


def pendingQueueCount() -> int:
    return _service.pending_count()


def flushOfflineQueue() -> None:
    _service.flush_offline_queue()


__all__ = [
    "apply_rules",
    "CheckInService",
    "QueueStore",
    "get_service",
    "getRoster",
    "upsertCheckIn",
    "getHistory",
    "getCheckIn",
    "getIdentity",
    "searchPersonnel",
    "listRoles",
    "listTeams",
    "setOffline",
    "pendingQueueCount",
    "flushOfflineQueue",
]
