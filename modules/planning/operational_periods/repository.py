"""Operational Periods repository — proxies through SARApp API (MongoDB backend)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional


def _iid() -> str:
    from utils.state import AppState
    v = AppState.get_active_incident()
    if not v:
        raise RuntimeError("No active incident configured")
    return str(v)


def _base() -> str:
    return f"/api/incidents/{_iid()}/planning/operational-periods"


def _client():
    from utils.api_client import api_client
    return api_client


def _parse_dt(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    text = str(value).strip().replace("Z", "+00:00")
    for candidate in (text, text.replace(" ", "T")):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None


@dataclass(slots=True)
class OperationalPeriodRecord:
    id: Optional[int] = None
    incident_id: str = ""
    number: int = 1
    name: str = ""
    status: str = "Planned"
    start_time: str = ""
    end_time: str = ""
    briefing_time: str = ""
    debrief_time: str = ""
    objectives: str = ""
    weather_summary: str = ""
    safety_message: str = ""
    created_at: str = ""
    updated_at: str = ""

    @property
    def code(self) -> str:
        return f"OP{self.number}"

    @property
    def display_name(self) -> str:
        return self.name.strip() or f"Operational Period {self.number}"


def _from_dict(d: dict) -> OperationalPeriodRecord:
    return OperationalPeriodRecord(
        id=d.get("id"),
        incident_id=d.get("incident_id", ""),
        number=int(d.get("number") or 1),
        name=str(d.get("name") or ""),
        status=str(d.get("status") or "Planned"),
        start_time=str(d.get("start_time") or ""),
        end_time=str(d.get("end_time") or ""),
        briefing_time=str(d.get("briefing_time") or ""),
        debrief_time=str(d.get("debrief_time") or ""),
        objectives=str(d.get("objectives") or ""),
        weather_summary=str(d.get("weather_summary") or ""),
        safety_message=str(d.get("safety_message") or ""),
        created_at=str(d.get("created_at") or ""),
        updated_at=str(d.get("updated_at") or ""),
    )


class OperationalPeriodRepository:
    STATUSES = ("Planned", "Active", "Complete", "Canceled")

    def __init__(self, incident_id: Optional[str] = None, db_path=None) -> None:
        from utils.state import AppState
        incident = incident_id or AppState.get_active_incident()
        if not incident:
            raise RuntimeError("No active incident configured")
        self.incident_id = str(incident)
        # db_path accepted but ignored — data lives in MongoDB via API

    def _base(self) -> str:
        return f"/api/incidents/{self.incident_id}/planning/operational-periods"

    def list_periods(self) -> list[OperationalPeriodRecord]:
        try:
            return [_from_dict(d) for d in _client().get(self._base())]
        except Exception:
            return []

    def list_period_choices(self) -> list[tuple[int, str]]:
        choices: list[tuple[int, str]] = []
        for period in self.list_periods():
            if period.id is None:
                continue
            label = f"OP {period.number}"
            if period.start_time:
                label += f" ({period.start_time}"
                if period.end_time:
                    label += f" - {period.end_time}"
                label += ")"
            choices.append((period.id, label))
        return choices

    def get_period(self, period_id: int) -> OperationalPeriodRecord:
        d = _client().get(f"{self._base()}/{period_id}")
        return _from_dict(d)

    def next_number(self) -> int:
        periods = self.list_periods()
        if not periods:
            return 1
        return max(p.number for p in periods) + 1

    def validate_no_overlap(self, start_time: str, end_time: str, *, exclude_id: Optional[int] = None) -> None:
        # Server-side validation will raise HTTPException on overlap; just check basic constraints here
        start_dt = _parse_dt(start_time)
        end_dt = _parse_dt(end_time)
        if start_dt is None or end_dt is None:
            raise ValueError("Start and end times are required.")
        if end_dt <= start_dt:
            raise ValueError("End time must be after start time.")

    def create_period(self, payload: dict[str, Any]) -> OperationalPeriodRecord:
        from utils.api_client import APIError
        try:
            d = _client().post(self._base(), json=payload)
            return _from_dict(d)
        except APIError as e:
            raise ValueError(str(e)) from e

    def update_period(self, period_id: int, payload: dict[str, Any]) -> OperationalPeriodRecord:
        from utils.api_client import APIError
        try:
            d = _client().patch(f"{self._base()}/{period_id}", json=payload)
            return _from_dict(d)
        except APIError as e:
            raise ValueError(str(e)) from e

    def clone_period(self, source_period_id: int) -> OperationalPeriodRecord:
        d = _client().post(f"{self._base()}/{source_period_id}/clone", json={})
        return _from_dict(d)

    def set_active_period(self, period_id: int) -> OperationalPeriodRecord:
        d = _client().post(f"{self._base()}/{period_id}/set-active", json={})
        from utils.state import AppState
        record = _from_dict(d)
        AppState.set_active_op_period(record.number)
        return record

    def get_active_period(self) -> Optional[OperationalPeriodRecord]:
        try:
            d = _client().get(f"{self._base()}/active")
            return _from_dict(d) if d else None
        except Exception:
            return None

    def period_summary(self, period_id: int) -> dict[str, int]:
        # Returns stub counts — accurate counts would require querying multiple collections
        return {"meetings": 0, "assignments": 0, "forms": 0, "objectives": 0}


__all__ = ["OperationalPeriodRecord", "OperationalPeriodRepository"]
