"""Dataclasses for CAP form templates and instances."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Tuple


@dataclass
class CapFormTemplate:
    id: int | None
    code: str
    title: str
    version: str | None
    json_schema: str
    layout_json: str
    is_active: int = 1

    @classmethod
    def from_row(cls, row: Tuple[Any, ...]) -> "CapFormTemplate":
        return cls(*row)

    def to_row(self) -> Tuple[Any, ...]:
        return tuple(self.__dict__.values())


@dataclass
class CapFormInstance:
    id: int | None
    template_id: int
    op_period_id: int | None
    code: str
    title: str | None
    data_json: str
    status: str
    version: int
    created_by_user_id: int | None
    created_utc: str
    updated_utc: str

    @classmethod
    def from_row(cls, row: Tuple[Any, ...]) -> "CapFormInstance":
        return cls(*row)

    def to_row(self) -> Tuple[Any, ...]:
        return tuple(self.__dict__.values())


@dataclass
class CapFormAttachment:
    id: int | None
    form_instance_id: int
    filename: str
    file_ref: str

    @classmethod
    def from_row(cls, row: Tuple[Any, ...]) -> "CapFormAttachment":
        return cls(*row)

    def to_row(self) -> Tuple[Any, ...]:
        return tuple(self.__dict__.values())
