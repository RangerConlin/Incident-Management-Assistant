"""Datamodels for the SARApp form creator module.

The dataclasses defined in this module describe the hybrid JSON structures
stored in the SQLite databases.  They are intentionally lightweight so they
can be easily serialised/deserialised without pulling in heavy ORM
dependencies.  The service layer primarily works with primitive dictionaries
so that existing modules that expect JSON friendly structures can continue to
operate without modification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Optional


BindingSource = Literal["static", "system"]
ValidationType = Literal["required", "regex", "range", "set"]
FieldType = Literal[
    "text",
    "multiline",
    "date",
    "time",
    "checkbox",
    "radio",
    "dropdown",
    "signature",
    "image",
    "table",
]


@dataclass(slots=True)
class Binding:
    """Describes a binding between a field and a data source."""

    source_type: BindingSource
    source_ref: str
    value: Optional[str] = None


@dataclass(slots=True)
class ValidationRule:
    """Validation rule to be applied to a field value."""

    rule_type: ValidationType
    rule_config: dict[str, Any]
    error_message: str


@dataclass(slots=True)
class FieldConfig:
    """Holds additional configuration for a field."""

    bindings: list[Binding] = field(default_factory=list)
    validations: list[ValidationRule] = field(default_factory=list)
    dropdown: Optional[dict[str, Any]] = None
    table: Optional[dict[str, Any]] = None


@dataclass(slots=True)
class Field:
    """Representation of a single form field."""

    id: Optional[int]
    page: int
    name: str
    type: FieldType
    x: float
    y: float
    width: float
    height: float
    font_family: str = ""
    font_size: int = 10
    align: str = "left"
    required: bool = False
    placeholder: str = ""
    mask: str = ""
    default_value: str = ""
    config: FieldConfig = field(default_factory=FieldConfig)


@dataclass(slots=True)
class Template:
    """Template metadata stored in the master database."""

    id: Optional[int]
    name: str
    category: Optional[str]
    subcategory: Optional[str]
    version: int
    background_path: str
    page_count: int
    schema_version: int
    fields: list[Field]
    created_at: datetime
    updated_at: datetime
    is_active: bool = True


@dataclass(slots=True)
class FormInstance:
    """Concrete instance of a template stored within an incident database."""

    id: Optional[int]
    incident_id: str
    template_id: int
    template_version: int
    status: str
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class InstanceValue:
    """Value captured for a field within a form instance."""

    id: Optional[int]
    instance_id: int
    field_id: int
    value: Any
    created_at: datetime
    updated_at: datetime
