from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class FormBindingDefinition:
    field_key: str
    binding_key: str
    source_module: str | None = None
    refresh_policy: str = "unlocked_only"


@dataclass(slots=True)
class BindingResult:
    key: str
    value: Any = None
    display_value: str | None = None
    source_type: str = "binding"
    source_module: str | None = None
    source_record_id: str | None = None
    confidence: float = 0.0
    error: str | None = None
