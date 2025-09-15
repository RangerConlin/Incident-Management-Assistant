from __future__ import annotations

"""Legacy forms renderer (deprecated).

Prefer using the deterministic export pipeline via
`modules.forms.FormRegistry` + `modules.forms.FormSession` +
`modules.forms.export_form`. This module remains for backwards
compatibility and CLI/demo use only.
"""

import warnings as _warnings
_warnings.warn(
    "modules.forms.render is deprecated; use FormRegistry/FormSession/export_form",
    DeprecationWarning,
    stacklevel=2,
)

from dataclasses import dataclass
from typing import Any, Dict, Optional
import json

from .templating import resolve_template, load_mapping
from .pdf_fill import fill_pdf
from .overlay import render_overlay

try:
    from jsonschema import Draft7Validator
except Exception:  # pragma: no cover - jsonschema is required
    Draft7Validator = None  # type: ignore


class FormValidationError(Exception):
    """Raised when input JSON fails schema validation."""


@dataclass
class RenderOptions:
    flatten: bool = True
    preview_png: bool = False


# helper to access nested dict via dot notation

def _get_value(data: Dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split('.'):  # simple dot notation
        if isinstance(current, list):
            # allow numeric index
            try:
                idx = int(part)
            except ValueError:
                raise KeyError(path)
            current = current[idx]
        else:
            current = current.get(part)
        if current is None:
            break
    return current


def _apply_mapping(data: Dict[str, Any], mapping: Dict[str, Any]) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    fields = mapping.get('fields', {})
    for target, source in fields.items():
        if isinstance(source, str):
            values[target] = _get_value(data, source)
        else:
            # unsupported expression; ignore for now
            values[target] = None
    return values


def render_form(
    form_id: str,
    form_version: str,
    data: Dict[str, Any],
    options: Optional[Dict[str, Any]] = None,
) -> bytes:
    """Render ``data`` for the given ``form_id`` and ``form_version``.

    Parameters
    ----------
    form_id: str
        Identifier such as ``"ics_205"``.
    form_version: str
        Template version, e.g. ``"2023.10"`` or ``"latest"``.
    data: Dict[str, Any]
        JSON-like dictionary with form values.
    options: Optional[Dict[str, Any]]
        Rendering options. Currently supports ``flatten``.
    """

    template = resolve_template(form_id, form_version)

    # Schema validation
    if template.schema_path and Draft7Validator is not None:
        schema = json.loads(template.schema_path.read_text())
        validator = Draft7Validator(schema)
        errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
        if errors:
            messages = "; ".join(f"{'.'.join(str(x) for x in err.path)}: {err.message}" for err in errors)
            raise FormValidationError(messages)

    mapping = load_mapping(template.mapping_path)
    field_values = _apply_mapping(data, mapping)

    if template.pdf_path and template.pdf_path.exists():
        pdf_bytes = fill_pdf(template.pdf_path, field_values, flatten=options.get('flatten', True) if options else True)
    else:
        pdf_bytes = render_overlay(field_values)
    return pdf_bytes

