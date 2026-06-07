from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

FieldType = Literal[
    "text", "multiline_text", "number", "integer", "date", "time", "datetime",
    "checkbox", "boolean", "select", "multi_select", "table", "repeater",
    "signature", "attachment_reference", "calculated", "hidden",
]


@dataclass(slots=True)
class FormValidationRule:
    rule_type: str
    value: Any = None
    message: str | None = None
    severity: str = "error"
    blocking: bool = True


@dataclass(slots=True)
class FormFieldDefinition:
    key: str
    label: str
    field_type: FieldType = "text"
    required: bool = False
    default_value: Any = None
    help_text: str | None = None
    section: str | None = None
    page: int | None = None
    order_index: int = 0
    options: list[Any] = field(default_factory=list)
    binding_key: str | None = None
    calculated: bool = False
    read_only: bool = False
    lock_on_finalize: bool = True
    validation_rules: list[FormValidationRule] = field(default_factory=list)
    layout: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.key or not self.key.strip():
            raise ValueError("field key is required")
        raw_id = self.layout.get("raw_field_id") if isinstance(self.layout, dict) else None
        if self.key == raw_id:
            raise ValueError("canonical field key must be stable and descriptive")
