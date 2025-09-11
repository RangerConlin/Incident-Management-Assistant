"""Dataclasses representing safety-related records stored in incident databases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple


@dataclass
class ICS208:
    id: int | None
    op_period_id: int
    title: str
    message: str
    created_utc: str
    updated_utc: str
    version: int = 1

    @classmethod
    def from_row(cls, row: Tuple[Any, ...]) -> "ICS208":
        return cls(*row)

    def to_row(self) -> Tuple[Any, ...]:
        return (
            self.id,
            self.op_period_id,
            self.title,
            self.message,
            self.created_utc,
            self.updated_utc,
            self.version,
        )


@dataclass
class ICS215AItem:
    id: int | None
    op_period_id: int
    task_id: int | None
    hazard_category: str
    hazard_description: str
    mitigation: str | None
    likelihood: str | None
    consequence: str | None
    residual_risk: str | None
    owner_user_id: int | None
    status: str
    location: str | None
    attachments_json: str | None
    created_utc: str
    updated_utc: str

    @classmethod
    def from_row(cls, row: Tuple[Any, ...]) -> "ICS215AItem":
        return cls(*row)

    def to_row(self) -> Tuple[Any, ...]:
        return tuple(self.__dict__.values())


@dataclass
class HazardLogItem:
    id: int | None
    op_period_id: int | None
    title: str
    category: str | None
    severity: str | None
    status: str
    location: str | None
    reported_by_user_id: int | None
    notes: str | None
    created_utc: str
    updated_utc: str

    @classmethod
    def from_row(cls, row: Tuple[Any, ...]) -> "HazardLogItem":
        return cls(*row)

    def to_row(self) -> Tuple[Any, ...]:
        return tuple(self.__dict__.values())


@dataclass
class SafetyBriefing:
    id: int | None
    op_period_id: int
    title: str
    content: str
    delivered_by_user_id: int | None
    delivered_utc: str

    @classmethod
    def from_row(cls, row: Tuple[Any, ...]) -> "SafetyBriefing":
        return cls(*row)

    def to_row(self) -> Tuple[Any, ...]:
        return tuple(self.__dict__.values())


@dataclass
class SafetyIncident:
    id: int | None
    op_period_id: int | None
    type: str
    description: str
    location: str | None
    severity: str | None
    reported_by_user_id: int | None
    treated_on_site: int
    referred_to_medical: int
    created_utc: str
    updated_utc: str

    @classmethod
    def from_row(cls, row: Tuple[Any, ...]) -> "SafetyIncident":
        return cls(*row)

    def to_row(self) -> Tuple[Any, ...]:
        return tuple(self.__dict__.values())


@dataclass
class PPEAdvisory:
    id: int | None
    op_period_id: int | None
    code: str
    label: str
    active: int
    notes: str | None
    created_utc: str
    updated_utc: str

    @classmethod
    def from_row(cls, row: Tuple[Any, ...]) -> "PPEAdvisory":
        return cls(*row)

    def to_row(self) -> Tuple[Any, ...]:
        return tuple(self.__dict__.values())
