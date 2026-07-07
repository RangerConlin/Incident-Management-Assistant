from __future__ import annotations

import csv
import tempfile
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QApplication

from modules.personnel.units_organizations.widgets.dialogs import NewOrganizationDialog
from utils.edit_menu_io import UnitsOrganizationsIO


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class _FakeApiClient:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.patched: list[tuple[str, dict[str, Any]]] = []
        self._next_id = 1

    def get(self, path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if path == "/api/master/types":
            return [
                {"id": 1, "name": "EMS"},
            ]
        if path == "/api/master/rank-structures":
            return [
                {"id": 10, "name": "EMS (Standard)"},
            ]
        if path == "/api/master/organizations":
            return [
                {
                    "id": 1,
                    "name": "Alpha Base",
                    "short_name": "ALPHA",
                    "parent_organization_id": None,
                    "organization_type_id": 1,
                    "default_rank_structure_id": 10,
                    "effective_rank_structure_id": 10,
                    "is_active": 1,
                    "notes": "Root note",
                    "external_id": "EXT-1",
                    "callsign_prefix": "A",
                    "sort_order": 0,
                },
                {
                    "id": 2,
                    "name": "Bravo Team",
                    "short_name": "BRV",
                    "parent_organization_id": 1,
                    "organization_type_id": 1,
                    "default_rank_structure_id": 10,
                    "effective_rank_structure_id": 10,
                    "is_active": 1,
                    "notes": "Child note",
                    "external_id": "EXT-2",
                    "callsign_prefix": "B",
                    "sort_order": 1,
                },
            ]
        raise AssertionError(f"Unexpected GET {path!r}")

    def post(self, path: str, json: dict[str, Any] | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if path == "/api/master/organizations":
            payload = dict(json or {})
            payload["int_id"] = self._next_id
            payload["id"] = self._next_id
            self._next_id += 1
            self.created.append(payload)
            return payload
        raise AssertionError(f"Unexpected POST {path!r}")

    def patch(self, path: str, json: dict[str, Any] | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.patched.append((path, dict(json or {})))
        return {}


def test_units_organizations_export_import_round_trip(monkeypatch) -> None:
    fake_api = _FakeApiClient()
    monkeypatch.setattr("utils.api_client.api_client", fake_api, raising=False)

    io = UnitsOrganizationsIO()
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
        export_path = io.export_csv(Path(temp_dir) / "units_orgs.csv")
        with export_path.open("r", encoding="utf-8", newline="") as fh:
            exported_rows = list(csv.DictReader(fh))

        assert exported_rows[0]["organization_type_name"] == "EMS"
        assert exported_rows[0]["rank_structure_name"] == "EMS (Standard)"
        assert exported_rows[1]["parent_name"] == "Alpha Base"
        assert exported_rows[1]["parent_short_name"] == "ALPHA"
        assert exported_rows[1]["organization_type_name"] == "EMS"
        assert exported_rows[1]["rank_structure_name"] == "EMS (Standard)"

        result = io.import_csv(export_path)

        assert result.inserted == 2
        assert result.errors == []
        assert len(fake_api.created) == 2
        assert fake_api.patched == [("/api/master/organizations/2", {"parent_organization_id": 1})]


def test_new_subunit_dialog_defaults_from_parent(monkeypatch) -> None:
    _ensure_app()
    org_type_id = 1
    rank_structure_id = 10

    class _FakeController:
        def list_organizations(self, include_inactive: bool = True) -> list[dict[str, Any]]:
            return [
                {"id": 1, "name": "Parent Unit", "short_name": "PARENT"},
            ]

        def list_organization_types(self, include_inactive: bool = True) -> list[dict[str, Any]]:
            return [{"id": org_type_id, "name": "EMS"}]

        def list_rank_structures(self, include_inactive: bool = True) -> list[dict[str, Any]]:
            return [{"id": rank_structure_id, "name": "EMS (Standard)"}]

        def get_organization(self, organization_id: int) -> dict[str, Any] | None:
            if organization_id != 1:
                return None
            return {
                "id": 1,
                "name": "Parent Unit",
                "short_name": "PARENT",
                "organization_type_id": org_type_id,
                "default_rank_structure_id": rank_structure_id,
                "effective_rank_structure_id": rank_structure_id,
            }

    dialog = NewOrganizationDialog(_FakeController(), parent_id=1)

    assert dialog.parent_combo.currentData() == 1
    assert dialog.org_type_combo.currentData() == org_type_id
    assert dialog.rank_structure_combo.currentData() == rank_structure_id
