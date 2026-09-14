from __future__ import annotations

import json
from pathlib import Path

from modules.forms_creator.form_set_registry import FormSetRegistry


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_mapping_row_groups_are_loaded_from_form_set_mapping(tmp_path):
    forms_root = tmp_path / "forms"
    _write_json(
        forms_root / "catalog.json",
        {
            "forms": [
                {
                    "id": "ics_203",
                    "number": "ICS 203",
                    "title": "Organization Assignment List",
                    "category": "Planning",
                    "row_groups": [{"id": "legacy_catalog_group", "data_key": "legacy"}],
                }
            ]
        },
    )
    _write_json(
        forms_root / "sets" / "fema" / "manifest.json",
        {"id": "fema", "display_name": "FEMA", "version": "2023", "fallback": None},
    )
    _write_json(
        forms_root / "sets" / "fema" / "ics_203" / "mapping.json",
        {
            "fields": [],
            "row_groups": [
                {
                    "ref": "org_branches",
                    "data_key": "org_branches",
                    "rows_per_page": [3],
                    "col_patterns": {"name": "branch_id{n}"},
                }
            ],
        },
    )

    registry = FormSetRegistry(forms_root)

    row_groups = registry.list_mapping_row_groups("ics_203", "fema")

    assert row_groups == [
        {
            "ref": "org_branches",
            "data_key": "org_branches",
            "rows_per_page": [3],
            "col_patterns": {"name": "branch_id{n}"},
        }
    ]
    assert registry.get_form_definition("ics_203").row_groups[0]["id"] == "legacy_catalog_group"
