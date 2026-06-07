from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class FormFamily:
    code: str
    title: str
    id: int | None = None
    description: str | None = None
    category: str | None = None
    default_agency: str | None = None
    is_active: bool = True
    created_at: str | None = None
    updated_at: str | None = None
