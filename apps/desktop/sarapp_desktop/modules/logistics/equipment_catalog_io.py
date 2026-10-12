"""Shared, Qt-free equipment master-catalog field list. Used by both the
desktop Edit-menu panel (`panels/equipment_edit_panel.py`) and the central
web GUI (`cloud_router/master_db/webgui.py`), so an exported file from one
is importable into the other.

No PySide6 import here — see `modules/personnel/catalog_io.py` for why that
matters (the web GUI runs inside cloud_router's process, which has no Qt
dependency).

Equipment's import/export is simpler than personnel's: each row maps
straight across to the API body with no grouping/parsing, so there is no
payload-builder function here, just the shared field list.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FieldSpec:
    key: str
    label: str
    required: bool = False
    in_export_default: bool = True


FIELDS: list[FieldSpec] = [
    FieldSpec("name", "Name", required=True),
    FieldSpec("type", "Type"),
    FieldSpec("id_number", "ID Number"),
    FieldSpec("serial_number", "Serial Number"),
    FieldSpec("organization", "Organization"),
    FieldSpec("condition", "Condition"),
    FieldSpec("notes", "Notes"),
]
FIELD_LABELS = {spec.key: spec.label for spec in FIELDS}
