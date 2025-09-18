"""Data models for the Forms Creator module.

These dataclasses act as an abstraction over the hybrid JSON payloads
stored in the SQLite databases.  They purposefully mirror the schema
outlined in the product specification so that the UI and service layers
can exchange structured objects without having to perform repetitive
parsing or dictionary lookups.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

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
class FieldBinding:
    """Represents a binding for a field.

    Attributes
    ----------
    source_type:
        Either ``"static"`` or ``"system"``.  ``system`` values are
        resolved via :class:`modules.forms_creator.services.binder.Binder`.
    source_ref:
        The dotted path that should be resolved when ``source_type`` is
        ``system``.  For ``static`` bindings this stores the literal
        value.
    meta:
        Optional metadata reserved for future use (e.g. transformation
        hints).  Stored verbatim in the JSON payload.
    """

    source_type: Literal["static", "system"]
    source_ref: str
    meta: dict[str, Any] | None = None


@dataclass(slots=True)
class FieldValidation:
    """Validation rule attached to a field."""

    rule_type: Literal["regex", "range", "set", "required"]
    rule_config: dict[str, Any] | None = None
    error_message: str | None = None


@dataclass(slots=True)
class Field:
    """Describes a single placed field on a template page."""

    id: int | None
    page: int
    name: str
    type: FieldType
    x: float
    y: float
    width: float
    height: float
    font_family: str = ""
    font_size: float = 10.0
    align: Literal["left", "center", "right"] = "left"
    required: bool = False
    placeholder: str = ""
    mask: str | None = None
    default_value: str | None = None
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialise the field to a dictionary for JSON storage."""

        bindings = [binding.__dict__ for binding in self.bindings]
        validations = [validation.__dict__ for validation in self.validations]
        payload = {
            "id": self.id,
            "page": self.page,
            "name": self.name,
            "type": self.type,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "font_family": self.font_family,
            "font_size": self.font_size,
            "align": self.align,
            "required": self.required,
            "placeholder": self.placeholder,
            "mask": self.mask,
            "default_value": self.default_value,
            "config": self.config | {
                "bindings": bindings,
                "validations": validations,
            },
        }
        return payload

    @property
    def bindings(self) -> list[FieldBinding]:
        """Return field bindings, initialising them when required."""

        bindings = self.config.get("bindings", [])
        if bindings and isinstance(bindings[0], FieldBinding):
            return bindings  # type: ignore[return-value]
        parsed = [FieldBinding(**binding) for binding in bindings]
        self.config["bindings"] = parsed
        return parsed

    @property
    def validations(self) -> list[FieldValidation]:
        """Return validation definitions for the field."""

        validations = self.config.get("validations", [])
        if validations and isinstance(validations[0], FieldValidation):
            return validations  # type: ignore[return-value]
        parsed = [FieldValidation(**validation) for validation in validations]
        self.config["validations"] = parsed
        return parsed


@dataclass(slots=True)
class Template:
    """Metadata describing a form template."""

    id: int
    name: str
    category: str | None
    subcategory: str | None
    version: int
    background_path: Path
    page_count: int
    schema_version: int
    fields: list[Field]
    created_at: datetime
    updated_at: datetime
    is_active: bool = True


@dataclass(slots=True)
class FormInstance:
    """Represents an instantiated template for a specific incident."""

    id: int
    incident_id: str
    template_id: int
    template_version: int
    status: Literal["draft", "finalized", "archived"]
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class InstanceValue:
    """Stores the value for a field on a form instance."""

    id: int
    instance_id: int
    field_id: int
    value: str | dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

